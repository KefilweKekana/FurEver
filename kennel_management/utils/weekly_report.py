"""
Automated Weekly Report — Feature #7
AI-generated PDF-ready report with shelter stats, adoption trends,
medical summaries, donor activity, and volunteer engagement.
"""
import frappe
from frappe.utils import (today, add_days, getdate, get_first_day, get_last_day,
                          cint, flt, add_months, fmt_money, now_datetime)


def generate_weekly_report():
    """Generate and email the weekly shelter intelligence report."""
    settings = frappe.get_single("Kennel Management Settings")
    shelter_name = getattr(settings, "shelter_name", "SPCA") or "SPCA"
    now = today()
    week_start = add_days(now, -7)

    report = _compile_weekly_data(now, week_start, shelter_name)
    html = _render_weekly_html(report, shelter_name, week_start, now)

    # Get recipients (managers + notification email)
    recipients = _get_report_recipients(settings)
    if not recipients:
        return

    frappe.sendmail(
        recipients=recipients,
        subject=f"📊 {shelter_name} Weekly Intelligence Report — {week_start} to {now}",
        message=html,
        now=True,
    )

    frappe.logger().info(f"Weekly report sent to {len(recipients)} recipients")


def _get_report_recipients(settings):
    recipients = set()
    notification_email = getattr(settings, "notification_email", None)
    if notification_email:
        recipients.add(notification_email)
    managers = frappe.get_all("Has Role",
        filters={"role": ["in", ["Kennel Manager", "System Manager"]], "parenttype": "User"},
        fields=["parent"], limit=50)
    for m in managers:
        user = frappe.db.get_value("User", m.parent, ["email", "enabled"], as_dict=True)
        if user and user.enabled:
            recipients.add(user.email)
    return list(recipients)


def _compile_weekly_data(now, week_start, shelter_name):
    """Compile all data for the weekly report."""
    data = {}

    # ── Population Trends ──
    data["current_population"] = frappe.db.count("Animal",
        {"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]})

    data["admissions_this_week"] = frappe.db.count("Animal Admission",
        {"creation": [">=", week_start], "docstatus": 1})

    data["outcomes_this_week"] = frappe.db.sql("""
        SELECT outcome_type, COUNT(*) as cnt
        FROM `tabAnimal`
        WHERE outcome_date >= %s AND outcome_date <= %s AND outcome_type IS NOT NULL
        GROUP BY outcome_type
    """, (week_start, now), as_dict=True)

    data["adoptions_this_week"] = frappe.db.count("Adoption Application",
        {"status": "Adoption Completed", "adoption_date": [">=", week_start]})

    # Compare to previous week
    prev_start = add_days(week_start, -7)
    data["adoptions_prev_week"] = frappe.db.count("Adoption Application",
        {"status": "Adoption Completed", "adoption_date": ["between", [prev_start, week_start]]})

    data["admissions_prev_week"] = frappe.db.count("Animal Admission",
        {"creation": ["between", [prev_start, week_start]], "docstatus": 1})

    # ── Adoption Pipeline ──
    data["pending_applications"] = frappe.db.count("Adoption Application",
        {"status": ["in", ["Pending", "Under Review"]]})
    data["approved_applications"] = frappe.db.count("Adoption Application",
        {"status": "Approved"})

    # Avg time to adoption this week
    avg_adoption = frappe.db.sql("""
        SELECT AVG(DATEDIFF(adoption_date, creation)) as avg_days
        FROM `tabAdoption Application`
        WHERE status = 'Adoption Completed' AND adoption_date >= %s
    """, week_start, as_dict=True)
    data["avg_adoption_days"] = round(flt(avg_adoption[0].avg_days)) if avg_adoption and avg_adoption[0].avg_days else None

    # ── Medical Summary ──
    data["vet_appointments"] = frappe.db.count("Veterinary Appointment",
        {"appointment_date": [">=", week_start], "status": ["!=", "Cancelled"]})

    data["vet_types"] = frappe.db.sql("""
        SELECT appointment_type, COUNT(*) as cnt
        FROM `tabVeterinary Appointment`
        WHERE appointment_date >= %s AND status != 'Cancelled'
        GROUP BY appointment_type ORDER BY cnt DESC LIMIT 8
    """, week_start, as_dict=True)

    data["animals_in_medical"] = frappe.db.count("Animal",
        {"status": ["in", ["Medical Hold", "In Treatment", "Quarantine"]]})

    # ── Kennel Utilization ──
    kennel_data = frappe.db.sql("""
        SELECT SUM(capacity) as cap, SUM(current_occupancy) as occ FROM `tabKennel`
    """, as_dict=True)
    data["kennel_capacity"] = cint(kennel_data[0].cap) if kennel_data else 0
    data["kennel_occupancy"] = cint(kennel_data[0].occ) if kennel_data else 0

    # ── Donations ──
    don_data = frappe.db.sql("""
        SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date >= %s
    """, week_start, as_dict=True)
    data["donations_count"] = cint(don_data[0].cnt) if don_data else 0
    data["donations_total"] = flt(don_data[0].total) if don_data else 0

    prev_don = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date BETWEEN %s AND %s
    """, (prev_start, week_start), as_dict=True)
    data["donations_prev_week"] = flt(prev_don[0].total) if prev_don else 0

    # ── Volunteer Activity ──
    data["active_volunteers"] = frappe.db.count("Volunteer", {"status": "Active"})

    # ── Long Stay Animals ──
    data["long_stay_30"] = frappe.db.count("Animal", {
        "status": "Available for Adoption",
        "intake_date": ["<=", add_days(now, -30)]
    })
    data["long_stay_60"] = frappe.db.count("Animal", {
        "status": "Available for Adoption",
        "intake_date": ["<=", add_days(now, -60)]
    })
    data["long_stay_90"] = frappe.db.count("Animal", {
        "status": "Available for Adoption",
        "intake_date": ["<=", add_days(now, -90)]
    })

    # ── Lost & Found ──
    data["lost_reports_open"] = frappe.db.count("Lost and Found Report",
        {"report_type": "Lost", "status": ["in", ["Open", "Investigating"]]})
    data["found_this_week"] = frappe.db.count("Lost and Found Report",
        {"report_type": "Found", "creation": [">=", week_start]})

    # ── Species breakdown ──
    data["species_breakdown"] = frappe.db.sql("""
        SELECT species, COUNT(*) as cnt FROM `tabAnimal`
        WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
        GROUP BY species ORDER BY cnt DESC
    """, as_dict=True)

    return data


def _render_weekly_html(data, shelter_name, week_start, now):
    """Render the weekly report as HTML email."""

    def trend_arrow(current, previous):
        if current > previous:
            return f"<span style='color:#22c55e;'>↑ {current - previous}</span>"
        elif current < previous:
            return f"<span style='color:#ef4444;'>↓ {previous - current}</span>"
        return "<span style='color:#6b7280;'>→ same</span>"

    def pct(val, total):
        return round(val / total * 100) if total else 0

    occ_pct = pct(data["kennel_occupancy"], data["kennel_capacity"])
    occ_color = "#22c55e" if occ_pct < 80 else "#f59e0b" if occ_pct < 95 else "#ef4444"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 750px; margin: 0 auto; color: #1f2937;">
        <div style="background: linear-gradient(135deg, #1e40af, #3b82f6); padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">📊 Weekly Intelligence Report</h1>
            <p style="color: #bfdbfe; margin: 4px 0 0 0;">{shelter_name} — {week_start} to {now}</p>
        </div>

        <div style="background: #f9fafb; padding: 24px; border: 1px solid #e5e7eb;">

            <!-- KEY METRICS -->
            <h2 style="color: #1e40af; font-size: 16px; margin-top: 0;">📈 Key Metrics</h2>
            <table style="width:100%; border-collapse:collapse; margin-bottom:20px;">
                <tr>
                    <td style="padding:12px; background:white; border:1px solid #e5e7eb; text-align:center; width:25%;">
                        <div style="font-size:32px; font-weight:bold; color:#7c3aed;">{data['current_population']}</div>
                        <div style="font-size:11px; color:#6b7280;">Animals In Care</div>
                    </td>
                    <td style="padding:12px; background:white; border:1px solid #e5e7eb; text-align:center; width:25%;">
                        <div style="font-size:32px; font-weight:bold; color:#22c55e;">{data['adoptions_this_week']}</div>
                        <div style="font-size:11px; color:#6b7280;">Adoptions {trend_arrow(data['adoptions_this_week'], data['adoptions_prev_week'])}</div>
                    </td>
                    <td style="padding:12px; background:white; border:1px solid #e5e7eb; text-align:center; width:25%;">
                        <div style="font-size:32px; font-weight:bold; color:#2563eb;">{data['admissions_this_week']}</div>
                        <div style="font-size:11px; color:#6b7280;">Admissions {trend_arrow(data['admissions_this_week'], data['admissions_prev_week'])}</div>
                    </td>
                    <td style="padding:12px; background:white; border:1px solid #e5e7eb; text-align:center; width:25%;">
                        <div style="font-size:32px; font-weight:bold; color:{occ_color};">{occ_pct}%</div>
                        <div style="font-size:11px; color:#6b7280;">Capacity ({data['kennel_occupancy']}/{data['kennel_capacity']})</div>
                    </td>
                </tr>
            </table>
    """

    # Adoption Pipeline
    html += f"""
            <h2 style="color: #1e40af; font-size: 16px;">🏠 Adoption Pipeline</h2>
            <table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:16px;">
                <tr style="background:#dbeafe;"><td style="padding:8px;">Pending Applications</td><td style="text-align:right;padding:8px;font-weight:bold;">{data['pending_applications']}</td></tr>
                <tr><td style="padding:8px;">Approved (Awaiting Pickup)</td><td style="text-align:right;padding:8px;font-weight:bold;">{data['approved_applications']}</td></tr>
                <tr style="background:#dbeafe;"><td style="padding:8px;">Completed This Week</td><td style="text-align:right;padding:8px;font-weight:bold;color:#22c55e;">{data['adoptions_this_week']}</td></tr>
                <tr><td style="padding:8px;">Avg. Days to Adoption</td><td style="text-align:right;padding:8px;font-weight:bold;">{data['avg_adoption_days'] or 'N/A'}</td></tr>
            </table>
    """

    # Medical
    if data.get("vet_types"):
        html += "<h2 style='color: #1e40af; font-size: 16px;'>🏥 Medical Activity</h2>"
        html += f"<p style='font-size:13px;'>{data['vet_appointments']} vet appointments | {data['animals_in_medical']} animals in medical care</p>"
        html += "<table style='width:100%; border-collapse:collapse; font-size:13px; margin-bottom:16px;'>"
        for v in data["vet_types"]:
            html += f"<tr><td style='padding:4px 8px;'>{v.appointment_type}</td><td style='text-align:right;padding:4px 8px;'>{v.cnt}</td></tr>"
        html += "</table>"

    # Long Stay
    html += f"""
            <h2 style="color: #1e40af; font-size: 16px;">⏰ Length of Stay</h2>
            <table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:16px;">
                <tr><td style="padding:6px 8px;">30+ days</td><td style="text-align:right;padding:6px 8px;color:#f59e0b;font-weight:bold;">{data['long_stay_30']}</td></tr>
                <tr style="background:#fef3c7;"><td style="padding:6px 8px;">60+ days</td><td style="text-align:right;padding:6px 8px;color:#f97316;font-weight:bold;">{data['long_stay_60']}</td></tr>
                <tr style="background:#fee2e2;"><td style="padding:6px 8px;">90+ days (critical)</td><td style="text-align:right;padding:6px 8px;color:#ef4444;font-weight:bold;">{data['long_stay_90']}</td></tr>
            </table>
    """

    # Donations
    don_trend = trend_arrow(int(data["donations_total"]), int(data["donations_prev_week"]))
    html += f"""
            <h2 style="color: #1e40af; font-size: 16px;">💰 Donations</h2>
            <p style="font-size:13px;">
                <strong>R {data['donations_total']:,.0f}</strong> from {data['donations_count']} donations {don_trend}
                (prev week: R {data['donations_prev_week']:,.0f})
            </p>
    """

    # Species breakdown
    if data.get("species_breakdown"):
        html += "<h2 style='color: #1e40af; font-size: 16px;'>🐾 Population by Species</h2>"
        html += "<table style='width:100%; border-collapse:collapse; font-size:13px; margin-bottom:16px;'>"
        for s in data["species_breakdown"]:
            bar_width = pct(s.cnt, data["current_population"])
            html += f"""<tr>
                <td style="padding:4px 8px; width:100px;">{s.species}</td>
                <td style="padding:4px;"><div style="background:#3b82f6;height:16px;width:{bar_width}%;border-radius:4px;"></div></td>
                <td style="padding:4px 8px; text-align:right; width:60px;">{s.cnt}</td>
            </tr>"""
        html += "</table>"

    # Lost & Found + Volunteers
    html += f"""
            <h2 style="color: #1e40af; font-size: 16px;">📋 Other Activity</h2>
            <table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:16px;">
                <tr><td style="padding:6px 8px;">Active Volunteers</td><td style="text-align:right;padding:6px 8px;">{data['active_volunteers']}</td></tr>
                <tr><td style="padding:6px 8px;">Open Lost Pet Reports</td><td style="text-align:right;padding:6px 8px;">{data['lost_reports_open']}</td></tr>
                <tr><td style="padding:6px 8px;">Found Reports This Week</td><td style="text-align:right;padding:6px 8px;">{data['found_this_week']}</td></tr>
            </table>
    """

    # Outcomes breakdown
    if data.get("outcomes_this_week"):
        html += "<h2 style='color: #1e40af; font-size: 16px;'>📤 Outcomes This Week</h2><ul style='font-size:13px;margin:0;padding-left:20px;'>"
        for o in data["outcomes_this_week"]:
            html += f"<li>{o.outcome_type}: {o.cnt}</li>"
        html += "</ul>"

    html += f"""
        </div>
        <div style="background: #1e40af; padding: 12px 24px; border-radius: 0 0 12px 12px; text-align: center;">
            <p style="color: #bfdbfe; margin: 0; font-size: 12px;">
                {shelter_name} Weekly Report — Generated {now_datetime().strftime('%Y-%m-%d %H:%M')} 🐾
            </p>
        </div>
    </div>
    """

    return html
