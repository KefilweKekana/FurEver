"""
Daily Shelter Briefing — Feature #1
Automated AI-enhanced morning email with overnight changes, today's schedule,
animals needing attention, capacity alerts, and actionable priorities.
"""
import frappe
from frappe.utils import today, add_days, getdate, now_datetime, cint, flt, fmt_money


def generate_daily_briefing():
    """Generate and send the AI-enhanced daily shelter briefing to staff."""
    settings = frappe.get_single("Kennel Management Settings")
    shelter_name = getattr(settings, "shelter_name", "SPCA") or "SPCA"
    now = today()
    yesterday = add_days(now, -1)

    briefing = _compile_briefing_data(now, yesterday, shelter_name)
    html = _render_briefing_html(briefing, shelter_name, now)

    # Send to notification email + all Kennel Manager users
    recipients = _get_briefing_recipients(settings)
    if not recipients:
        return

    frappe.sendmail(
        recipients=recipients,
        subject=f"🌅 {shelter_name} Daily Briefing — {now}",
        message=html,
        now=True,
    )

    frappe.logger().info(f"Daily briefing sent to {len(recipients)} recipients")


def _get_briefing_recipients(settings):
    """Get list of email recipients for the briefing."""
    recipients = set()

    notification_email = getattr(settings, "notification_email", None)
    if notification_email:
        recipients.add(notification_email)

    # All Kennel Managers
    managers = frappe.get_all("Has Role", filters={"role": "Kennel Manager", "parenttype": "User"},
                              fields=["parent"], limit=50)
    for m in managers:
        user = frappe.db.get_value("User", m.parent, ["email", "enabled"], as_dict=True)
        if user and user.enabled:
            recipients.add(user.email)

    return list(recipients)


def _compile_briefing_data(now, yesterday, shelter_name):
    """Compile all briefing data sections."""
    data = {}

    # ── Overnight Changes (since yesterday 5pm) ──
    data["new_admissions"] = frappe.get_all("Animal Admission",
        filters={"creation": [">=", f"{yesterday} 17:00:00"], "docstatus": 1},
        fields=["name", "animal_name", "species", "breed", "admission_type"],
        order_by="creation desc", limit=20)

    data["status_changes"] = frappe.db.sql("""
        SELECT name, animal_name, status, modified
        FROM `tabAnimal`
        WHERE modified >= %s AND modified > creation
        ORDER BY modified DESC LIMIT 20
    """, f"{yesterday} 17:00:00", as_dict=True)

    data["new_applications"] = frappe.get_all("Adoption Application",
        filters={"creation": [">=", f"{yesterday} 17:00:00"]},
        fields=["name", "applicant_name", "animal_name", "status"],
        order_by="creation desc", limit=10)

    # ── Current Population ──
    data["total_animals"] = frappe.db.count("Animal",
        {"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]})

    data["status_breakdown"] = frappe.db.sql("""
        SELECT status, COUNT(*) as cnt FROM `tabAnimal`
        WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
        GROUP BY status ORDER BY cnt DESC
    """, as_dict=True)

    data["species_breakdown"] = frappe.db.sql("""
        SELECT species, COUNT(*) as cnt FROM `tabAnimal`
        WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
        GROUP BY species ORDER BY cnt DESC
    """, as_dict=True)

    # ── Kennel Capacity ──
    kennel_stats = frappe.db.sql("""
        SELECT SUM(capacity) as total_cap, SUM(current_occupancy) as total_occ
        FROM `tabKennel`
    """, as_dict=True)
    data["kennel_capacity"] = cint(kennel_stats[0].total_cap) if kennel_stats else 0
    data["kennel_occupancy"] = cint(kennel_stats[0].total_occ) if kennel_stats else 0
    data["occupancy_rate"] = round(data["kennel_occupancy"] / data["kennel_capacity"] * 100) if data["kennel_capacity"] else 0

    data["full_kennels"] = frappe.db.sql("""
        SELECT kennel_name FROM `tabKennel`
        WHERE current_occupancy >= capacity AND status = 'Available'
    """, as_dict=True)

    # ── Today's Schedule ──
    data["vet_appointments"] = frappe.get_all("Veterinary Appointment",
        filters={"appointment_date": now, "status": ["!=", "Cancelled"]},
        fields=["animal_name", "appointment_type", "appointment_time", "priority", "veterinarian"],
        order_by="appointment_time asc", limit=30)

    # ── Animals Needing Attention ──
    # Long-stay (>30 days)
    data["long_stay"] = frappe.db.sql("""
        SELECT name, animal_name, species, breed, intake_date,
               DATEDIFF(%s, intake_date) as days_in_shelter
        FROM `tabAnimal`
        WHERE status = 'Available for Adoption' AND intake_date <= %s
        ORDER BY intake_date ASC LIMIT 15
    """, (now, add_days(now, -30)), as_dict=True)

    # Medical hold animals
    data["medical_hold"] = frappe.get_all("Animal",
        filters={"status": ["in", ["Medical Hold", "In Treatment", "Quarantine"]]},
        fields=["name", "animal_name", "species", "status", "medical_notes"],
        order_by="animal_name", limit=20)

    # Vaccinations due within 3 days
    data["vaccinations_due"] = frappe.db.sql("""
        SELECT vi.parent, vi.vaccination_type, vi.next_due_date,
               a.animal_name, a.species
        FROM `tabVaccination Item` vi
        JOIN `tabAnimal` a ON vi.parent = a.name
        WHERE vi.next_due_date BETWEEN %s AND %s
              AND a.status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
        ORDER BY vi.next_due_date
        LIMIT 20
    """, (now, add_days(now, 3)), as_dict=True)

    # ── Recent Adoptions (last 7 days) ──
    data["recent_adoptions"] = frappe.db.sql("""
        SELECT applicant_name, animal_name, adoption_date
        FROM `tabAdoption Application`
        WHERE status = 'Adoption Completed' AND adoption_date >= %s
        ORDER BY adoption_date DESC LIMIT 10
    """, add_days(now, -7), as_dict=True)

    # ── Donation summary (yesterday) ──
    data["yesterday_donations"] = frappe.db.sql("""
        SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date = %s
    """, yesterday, as_dict=True)

    # ── Lost/Found alerts ──
    data["open_lost_reports"] = frappe.db.count("Lost and Found Report",
        {"report_type": "Lost", "status": ["in", ["Open", "Investigating"]]})

    return data


def _render_briefing_html(data, shelter_name, now):
    """Render the briefing data into an HTML email."""
    occ_color = "#22c55e" if data["occupancy_rate"] < 80 else "#f59e0b" if data["occupancy_rate"] < 95 else "#ef4444"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; color: #1f2937;">
        <div style="background: linear-gradient(135deg, #7c3aed, #a855f7); padding: 20px 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 22px;">🌅 Good Morning, {shelter_name} Team!</h1>
            <p style="color: #e9d5ff; margin: 4px 0 0 0; font-size: 14px;">Daily Briefing — {now}</p>
        </div>

        <div style="background: #f9fafb; padding: 20px 24px; border: 1px solid #e5e7eb;">

            <!-- Population Snapshot -->
            <h2 style="color: #7c3aed; font-size: 16px; margin-top: 0;">📊 Population Snapshot</h2>
            <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px;">
                <div style="background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e5e7eb; flex: 1; min-width: 120px; text-align: center;">
                    <div style="font-size: 28px; font-weight: bold; color: #7c3aed;">{data['total_animals']}</div>
                    <div style="font-size: 12px; color: #6b7280;">Animals In Care</div>
                </div>
                <div style="background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e5e7eb; flex: 1; min-width: 120px; text-align: center;">
                    <div style="font-size: 28px; font-weight: bold; color: {occ_color};">{data['occupancy_rate']}%</div>
                    <div style="font-size: 12px; color: #6b7280;">Kennel Capacity ({data['kennel_occupancy']}/{data['kennel_capacity']})</div>
                </div>
                <div style="background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e5e7eb; flex: 1; min-width: 120px; text-align: center;">
                    <div style="font-size: 28px; font-weight: bold; color: #2563eb;">{len(data.get('vet_appointments', []))}</div>
                    <div style="font-size: 12px; color: #6b7280;">Vet Appointments Today</div>
                </div>
            </div>

            <!-- Status Breakdown -->
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 13px;">
                <tr style="background: #f3f4f6;"><td style="padding: 6px 10px;" colspan="2"><strong>By Status</strong></td>
                    <td style="padding: 6px 10px;" colspan="2"><strong>By Species</strong></td></tr>
    """

    # Build status + species side by side
    status_rows = data.get("status_breakdown", [])
    species_rows = data.get("species_breakdown", [])
    max_rows = max(len(status_rows), len(species_rows))
    for i in range(max_rows):
        s = status_rows[i] if i < len(status_rows) else None
        sp = species_rows[i] if i < len(species_rows) else None
        html += "<tr>"
        html += f"<td style='padding:4px 10px;'>{s.status if s else ''}</td><td style='padding:4px 10px;text-align:right;'>{s.cnt if s else ''}</td>"
        html += f"<td style='padding:4px 10px;'>{sp.species if sp else ''}</td><td style='padding:4px 10px;text-align:right;'>{sp.cnt if sp else ''}</td>"
        html += "</tr>"

    html += "</table>"

    # ── Overnight Changes ──
    overnight_items = []
    for a in data.get("new_admissions", []):
        overnight_items.append(f"🆕 New admission: <strong>{a.animal_name}</strong> ({a.species}/{a.breed or '?'}) — {a.admission_type}")
    for a in data.get("new_applications", []):
        overnight_items.append(f"📝 New adoption application: <strong>{a.applicant_name}</strong> for {a.animal_name or 'unspecified'}")
    for a in data.get("status_changes", []):
        overnight_items.append(f"🔄 Status changed: <strong>{a.animal_name}</strong> → {a.status}")

    if overnight_items:
        html += "<h2 style='color: #7c3aed; font-size: 16px;'>🌙 Overnight Changes</h2><ul style='margin:0; padding-left:20px;'>"
        for item in overnight_items[:15]:
            html += f"<li style='margin-bottom:4px; font-size:13px;'>{item}</li>"
        html += "</ul>"

    # ── Today's Vet Schedule ──
    if data.get("vet_appointments"):
        html += "<h2 style='color: #7c3aed; font-size: 16px;'>🏥 Today's Vet Schedule</h2>"
        html += "<table style='width:100%; border-collapse:collapse; font-size:13px;'>"
        html += "<tr style='background:#f3f4f6;'><th style='padding:6px;text-align:left;'>Time</th><th style='text-align:left;padding:6px;'>Animal</th><th style='text-align:left;padding:6px;'>Type</th><th style='text-align:left;padding:6px;'>Priority</th></tr>"
        for a in data["vet_appointments"]:
            time_str = str(a.appointment_time or "")[:5] or "TBD"
            priority_color = "#ef4444" if a.priority == "Emergency" else "#f59e0b" if a.priority == "Urgent" else "#6b7280"
            html += f"<tr><td style='padding:4px 6px;'>{time_str}</td><td style='padding:4px 6px;'>{a.animal_name}</td>"
            html += f"<td style='padding:4px 6px;'>{a.appointment_type}</td>"
            html += f"<td style='padding:4px 6px;color:{priority_color};font-weight:bold;'>{a.priority}</td></tr>"
        html += "</table>"

    # ── Attention Needed ──
    attention_items = []
    for a in data.get("medical_hold", []):
        attention_items.append(f"🏥 <strong>{a.animal_name}</strong> ({a.species}) — {a.status}")
    for v in data.get("vaccinations_due", []):
        attention_items.append(f"💉 <strong>{v.animal_name}</strong> — {v.vaccination_type} due {v.next_due_date}")
    for a in data.get("long_stay", [])[:5]:
        attention_items.append(f"⏰ <strong>{a.animal_name}</strong> ({a.species}/{a.breed or '?'}) — {a.days_in_shelter} days in shelter")

    if attention_items:
        html += "<h2 style='color: #7c3aed; font-size: 16px;'>⚠️ Needs Attention</h2><ul style='margin:0; padding-left:20px;'>"
        for item in attention_items[:20]:
            html += f"<li style='margin-bottom:4px; font-size:13px;'>{item}</li>"
        html += "</ul>"

    # ── Full Kennels ──
    if data.get("full_kennels"):
        names = ", ".join([k.kennel_name for k in data["full_kennels"]])
        html += f"<p style='color:#ef4444; font-size:13px;'>🚫 <strong>Full kennels:</strong> {names}</p>"

    # ── Good News ──
    if data.get("recent_adoptions"):
        html += "<h2 style='color: #7c3aed; font-size: 16px;'>🎉 Recent Adoptions (7 days)</h2><ul style='margin:0; padding-left:20px;'>"
        for a in data["recent_adoptions"]:
            html += f"<li style='font-size:13px;'>{a.animal_name} → {a.applicant_name} ({a.adoption_date})</li>"
        html += "</ul>"

    # ── Quick Stats Footer ──
    don = data.get("yesterday_donations", [{}])[0] if data.get("yesterday_donations") else {}
    don_total = flt(don.get("total", 0))
    don_cnt = cint(don.get("cnt", 0))

    html += f"""
            <div style="margin-top: 20px; padding: 12px 16px; background: #ede9fe; border-radius: 8px; font-size: 13px;">
                <strong>Yesterday's Donations:</strong> R {don_total:,.0f} ({don_cnt} donation{'s' if don_cnt != 1 else ''})
                &nbsp;|&nbsp; <strong>Open Lost Reports:</strong> {data.get('open_lost_reports', 0)}
            </div>
        </div>

        <div style="background: #7c3aed; padding: 12px 24px; border-radius: 0 0 12px 12px; text-align: center;">
            <p style="color: #e9d5ff; margin: 0; font-size: 12px;">
                {shelter_name} Kennel Management System — Have a great day! 🐾
            </p>
        </div>
    </div>
    """

    return html
