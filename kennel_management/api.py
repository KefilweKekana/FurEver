import frappe
from frappe import _


@frappe.whitelist()
def get_available_kennel(species=None, requires_quarantine=False):
    """Find the best available kennel for a new animal."""
    filters = {
        "status": "Available",
    }

    if requires_quarantine or str(requires_quarantine) == "1":
        filters["is_quarantine"] = 1

    kennels = frappe.get_all(
        "Kennel",
        filters=filters,
        fields=["name", "kennel_name", "capacity", "current_occupancy", "kennel_type", "section"],
        order_by="current_occupancy asc",
    )

    for kennel in kennels:
        if kennel.current_occupancy < kennel.capacity:
            return kennel.name

    return None


@frappe.whitelist()
def get_dashboard_stats():
    """Get statistics for the kennel management dashboard."""
    stats = {
        "total_animals": frappe.db.count(
            "Animal",
            filters={"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]},
        ),
        "available_for_adoption": frappe.db.count(
            "Animal", filters={"status": "Available for Adoption"}
        ),
        "in_medical_hold": frappe.db.count(
            "Animal", filters={"status": "Medical Hold"}
        ),
        "in_quarantine": frappe.db.count(
            "Animal", filters={"status": "Quarantine"}
        ),
        "in_foster": frappe.db.count(
            "Animal", filters={"status": "In Foster Care"}
        ),
        "pending_adoptions": frappe.db.count(
            "Adoption Application", filters={"status": ["in", ["Pending", "Under Review"]]}
        ),
        "scheduled_appointments": frappe.db.count(
            "Veterinary Appointment", filters={"status": "Scheduled"}
        ),
        "total_kennels": frappe.db.count("Kennel"),
        "available_kennels": frappe.db.count("Kennel", filters={"status": "Available"}),
        "adoptions_this_month": get_monthly_adoptions(),
        "admissions_this_month": get_monthly_admissions(),
    }
    return stats


def get_monthly_adoptions():
    from frappe.utils import get_first_day, today

    return frappe.db.count(
        "Animal",
        filters={
            "outcome_type": "Adoption",
            "outcome_date": [">=", get_first_day(today())],
        },
    )


def get_monthly_admissions():
    from frappe.utils import get_first_day, today

    return frappe.db.count(
        "Animal Admission",
        filters={
            "docstatus": 1,
            "admission_date": [">=", get_first_day(today())],
        },
    )


@frappe.whitelist()
def get_animals_for_daily_round(section=None):
    """Get all active animals for daily round, optionally filtered by section."""
    filters = {
        "status": [
            "not in",
            ["Adopted", "Transferred", "Deceased", "Returned to Owner"],
        ],
    }
    if section:
        filters["kennel_section_area"] = section

    return frappe.get_all(
        "Animal",
        filters=filters,
        fields=["name", "animal_name", "species", "breed", "current_kennel", "status"],
        order_by="current_kennel asc, animal_name asc",
    )


@frappe.whitelist()
def send_sms_dialog(phone, doctype, name):
    """Send SMS to a phone number."""
    settings = frappe.get_single("Kennel Management Settings")
    if not settings.enable_sms:
        frappe.throw(_("SMS is not enabled. Configure it in Kennel Management Settings."))

    from kennel_management.utils.messaging import send_sms

    message = frappe.form_dict.get("message", "")
    if message:
        send_sms(phone, message)
        return True
    return False


@frappe.whitelist()
def get_animal_timeline(animal):
    """Get full timeline of events for an animal."""
    timeline = []

    # Admissions
    admissions = frappe.get_all(
        "Animal Admission",
        filters={"animal": animal, "docstatus": 1},
        fields=["name", "admission_date", "admission_type"],
    )
    for a in admissions:
        timeline.append({
            "date": str(a.admission_date),
            "type": "Admission",
            "description": f"{a.admission_type} - {a.name}",
        })

    # Vet appointments
    appointments = frappe.get_all(
        "Veterinary Appointment",
        filters={"animal": animal},
        fields=["name", "appointment_date", "appointment_type", "status"],
    )
    for a in appointments:
        timeline.append({
            "date": str(a.appointment_date),
            "type": "Vet Appointment",
            "description": f"{a.appointment_type} ({a.status}) - {a.name}",
        })

    # Medical records
    records = frappe.get_all(
        "Veterinary Record",
        filters={"animal": animal, "docstatus": 1},
        fields=["name", "date", "record_type", "description"],
    )
    for r in records:
        timeline.append({
            "date": str(r.date),
            "type": "Medical Record",
            "description": f"{r.record_type} - {r.name}",
        })

    # Behavior assessments
    assessments = frappe.get_all(
        "Behavior Assessment",
        filters={"animal": animal},
        fields=["name", "assessment_date", "overall_temperament", "overall_score"],
    )
    for ba in assessments:
        timeline.append({
            "date": str(ba.assessment_date),
            "type": "Behavior Assessment",
            "description": f"Temperament: {ba.overall_temperament or 'N/A'} - {ba.name}",
        })

    timeline.sort(key=lambda x: x["date"], reverse=True)
    return timeline


@frappe.whitelist()
def get_dashboard_data(period="today"):
    """Get comprehensive dashboard data for the kennel dashboard page."""
    from frappe.utils import (
        today, nowdate, add_days, add_months, get_first_day,
        getdate, now_datetime, fmt_money
    )

    now = today()
    first_day = get_first_day(now)

    # Date range based on period
    if period == "today":
        start_date = now
    elif period == "week":
        start_date = add_days(now, -7)
    else:  # month
        start_date = first_day

    prev_start = add_days(start_date, -(getdate(now) - getdate(start_date)).days or -1)

    # === STATS ===
    total_animals = frappe.db.count(
        "Animal",
        filters={"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]}
    )

    prev_total = frappe.db.count(
        "Animal",
        filters={
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            "creation": ["<", start_date]
        }
    )

    available = frappe.db.count("Animal", filters={"status": "Available for Adoption"})

    adoptions = frappe.db.count(
        "Adoption Application",
        filters={"status": "Adoption Completed", "modified": [">=", start_date]}
    )

    prev_adoptions = frappe.db.count(
        "Adoption Application",
        filters={"status": "Adoption Completed", "modified": ["between", [prev_start, start_date]]}
    )

    # Kennel occupancy
    kennel_data = frappe.db.sql(
        "SELECT SUM(capacity) as total_cap, SUM(current_occupancy) as total_occ FROM `tabKennel`",
        as_dict=True
    )
    total_cap = (kennel_data[0].total_cap or 0) if kennel_data else 0
    total_occ = (kennel_data[0].total_occ or 0) if kennel_data else 0
    occupancy_rate = round((total_occ / total_cap * 100) if total_cap else 0)

    # Vet today
    vet_today = frappe.db.count(
        "Veterinary Appointment",
        filters={"appointment_date": now, "status": ["!=", "Cancelled"]}
    )
    vet_urgent = frappe.db.count(
        "Veterinary Appointment",
        filters={"appointment_date": now, "appointment_type": "Emergency"}
    )

    # Donations
    donation_data = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) as total FROM `tabDonation`
        WHERE docstatus = 1 AND donation_date >= %(first_day)s""",
        {"first_day": first_day},
        as_dict=True
    )
    donations_amount = (donation_data[0].total or 0) if donation_data else 0

    prev_donation_data = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) as total FROM `tabDonation`
        WHERE docstatus = 1 AND donation_date BETWEEN %(prev_start)s AND %(first_day)s""",
        {"prev_start": add_months(first_day, -1), "first_day": first_day},
        as_dict=True
    )
    prev_donations = (prev_donation_data[0].total or 0) if prev_donation_data else 0

    donations_trend = None
    if prev_donations:
        donations_trend = round(((donations_amount - prev_donations) / prev_donations) * 100)

    stats = {
        "total_animals": total_animals,
        "animals_trend": total_animals - prev_total if prev_total else None,
        "available": available,
        "adoptions": adoptions,
        "adoptions_trend": adoptions - prev_adoptions if prev_adoptions is not None else None,
        "occupancy_rate": occupancy_rate,
        "vet_today": vet_today,
        "vet_urgent": vet_urgent if vet_urgent else None,
        "donations_amount": float(donations_amount),
        "donations_trend": donations_trend
    }

    # === CHART DATA: Intake & Adoptions (last 6 months) ===
    intake_data = []
    adoption_data = []
    for i in range(5, -1, -1):
        month_start = add_months(get_first_day(now), -i)
        month_end = add_days(add_months(month_start, 1), -1)
        label = getdate(month_start).strftime("%b")

        intake_count = frappe.db.count(
            "Animal Admission",
            filters={"docstatus": 1, "admission_date": ["between", [month_start, month_end]]}
        )
        adopt_count = frappe.db.count(
            "Adoption Application",
            filters={"status": "Adoption Completed", "modified": ["between", [month_start, month_end]]}
        )
        intake_data.append({"label": label, "value": intake_count})
        adoption_data.append({"label": label, "value": adopt_count})

    # === CHART DATA: Species breakdown ===
    species_raw = frappe.db.sql(
        """SELECT species, COUNT(*) as cnt FROM `tabAnimal`
        WHERE status NOT IN ('Adopted', 'Transferred', 'Deceased', 'Returned to Owner')
        GROUP BY species ORDER BY cnt DESC""",
        as_dict=True
    )
    species_data = [{"label": s.species or "Unknown", "value": s.cnt} for s in species_raw]

    # === RECENT ACTIVITY ===
    recent_activity = []

    admissions = frappe.get_all(
        "Animal Admission",
        filters={"docstatus": 1},
        fields=["name", "animal_name_field", "admission_type", "creation"],
        order_by="creation desc",
        limit=5
    )
    for a in admissions:
        recent_activity.append({
            "type": "admission",
            "description": f"New {a.admission_type}: {a.animal_name_field}",
            "date": str(a.creation)
        })

    recent_adoptions = frappe.get_all(
        "Adoption Application",
        filters={"status": "Adoption Completed"},
        fields=["name", "applicant_name", "creation", "modified"],
        order_by="modified desc",
        limit=3
    )
    for a in recent_adoptions:
        recent_activity.append({
            "type": "adoption",
            "description": f"Adopted by {a.applicant_name}",
            "date": str(a.modified)
        })

    recent_donations = frappe.get_all(
        "Donation",
        filters={"docstatus": 1},
        fields=["name", "donor_name", "amount", "creation"],
        order_by="creation desc",
        limit=3
    )
    for d in recent_donations:
        recent_activity.append({
            "type": "donation",
            "description": f"R {d.amount:,.0f} from {d.donor_name or 'Anonymous'}",
            "date": str(d.creation)
        })

    recent_activity.sort(key=lambda x: x["date"], reverse=True)
    recent_activity = recent_activity[:8]

    # === TODAY'S APPOINTMENTS ===
    todays_appointments = frappe.get_all(
        "Veterinary Appointment",
        filters={"appointment_date": now, "status": ["!=", "Cancelled"]},
        fields=["name", "animal", "animal_name", "appointment_type", "appointment_time", "status"],
        order_by="appointment_time asc"
    )
    for appt in todays_appointments:
        if appt.appointment_time:
            appt["time"] = str(appt.appointment_time)[:5]
        else:
            appt["time"] = "--:--"

    # === PENDING APPLICATIONS ===
    pending_applications = frappe.get_all(
        "Adoption Application",
        filters={"status": ["in", ["Pending", "Under Review"]]},
        fields=["name", "applicant_name", "species_preference", "creation"],
        order_by="creation asc",
        limit=6
    )

    return {
        "stats": stats,
        "intake_data": intake_data,
        "adoption_data": adoption_data,
        "species_data": species_data,
        "recent_activity": recent_activity,
        "todays_appointments": todays_appointments,
        "pending_applications": pending_applications
    }


@frappe.whitelist()
def chatbot_query(message):
    """Process chatbot queries — built-in shelter data + optional AI integration."""
    from frappe.utils import today, getdate, add_days, get_first_day, flt, cint

    message_lower = (message or "").strip().lower()
    now = today()

    # Try built-in intent matching first
    result = _match_intent(message_lower, now)

    if result:
        return result

    # If no intent matched, try AI if configured
    ai_reply = _try_ai_query(message)
    if ai_reply:
        return ai_reply

    # Fallback
    return {
        "reply": (
            "I'm not sure how to answer that yet. Here are some things I can help with:\n\n"
            "• **Animal counts** — how many animals, species breakdown\n"
            "• **Kennel occupancy** — capacity and availability\n"
            "• **Vet appointments** — today's schedule\n"
            "• **Adoptions** — pending applications, completed\n"
            "• **Recent admissions** — latest intake\n"
            "• **Donations** — this month's totals\n\n"
            "Try asking one of these, or use the quick action buttons above!"
        ),
        "actions": []
    }


def _match_intent(msg, now):
    """Match message to a built-in shelter data query."""
    from frappe.utils import get_first_day, flt, cint

    # --- Animal counts ---
    if any(k in msg for k in ["how many animal", "animal count", "total animal", "animals in"]):
        total = frappe.db.count("Animal", {"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]})
        available = frappe.db.count("Animal", {"status": "Available for Adoption"})
        quarantine = frappe.db.count("Animal", {"status": "Quarantine"})
        medical = frappe.db.count("Animal", {"status": "Medical Hold"})

        return {
            "reply": (
                f"There are currently **{total} animals** in the shelter:\n\n"
                f"• **{available}** available for adoption\n"
                f"• **{quarantine}** in quarantine\n"
                f"• **{medical}** on medical hold"
            ),
            "actions": [
                {"label": "View All Animals", "route": "/app/animal"},
                {"label": "Available for Adoption", "route": "/app/animal?status=Available+for+Adoption"}
            ]
        }

    # --- Species breakdown ---
    if any(k in msg for k in ["species", "breed", "what types", "dogs and cats"]):
        species = frappe.db.sql(
            """SELECT species, COUNT(*) as cnt FROM `tabAnimal`
            WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
            GROUP BY species ORDER BY cnt DESC""",
            as_dict=True
        )
        if species:
            lines = "\n".join([f"• **{s.species or 'Unknown'}**: {s.cnt}" for s in species])
            return {
                "reply": f"Here's the species breakdown:\n\n{lines}",
                "actions": [{"label": "View Animals", "route": "/app/animal"}]
            }
        return {"reply": "No animals currently in the shelter.", "actions": []}

    # --- Kennel occupancy ---
    if any(k in msg for k in ["kennel", "occupancy", "capacity", "space", "room"]):
        data = frappe.db.sql(
            "SELECT SUM(capacity) as cap, SUM(current_occupancy) as occ FROM `tabKennel`",
            as_dict=True
        )
        cap = cint(data[0].cap) if data else 0
        occ = cint(data[0].occ) if data else 0
        avail_kennels = frappe.db.count("Kennel", {"status": "Available"})
        rate = round(occ / cap * 100) if cap else 0

        return {
            "reply": (
                f"**Kennel Occupancy: {rate}%**\n\n"
                f"• Total capacity: {cap} animals\n"
                f"• Currently housed: {occ}\n"
                f"• Available spaces: {cap - occ}\n"
                f"• Available kennels: {avail_kennels}"
            ),
            "actions": [{"label": "View Kennels", "route": "/app/kennel"}]
        }

    # --- Vet appointments ---
    if any(k in msg for k in ["vet", "appointment", "veterinary", "medical schedule"]):
        appts = frappe.get_all(
            "Veterinary Appointment",
            filters={"appointment_date": now, "status": ["!=", "Cancelled"]},
            fields=["animal_name", "appointment_type", "appointment_time", "status"],
            order_by="appointment_time asc",
            limit=10
        )
        if appts:
            lines = []
            for a in appts:
                time_str = str(a.appointment_time or "")[:5] or "--:--"
                lines.append(f"• **{time_str}** — {a.animal_name}: {a.appointment_type} ({a.status})")
            return {
                "reply": f"Today's vet appointments ({len(appts)}):\n\n" + "\n".join(lines),
                "actions": [{"label": "View All Appointments", "route": "/app/veterinary-appointment"}]
            }
        return {
            "reply": "No vet appointments scheduled for today. 🎉",
            "actions": [{"label": "Schedule Appointment", "route": "/app/veterinary-appointment/new"}]
        }

    # --- Adoptions / pending ---
    if any(k in msg for k in ["adoption", "pending app", "application"]):
        pending = frappe.db.count("Adoption Application", {"status": ["in", ["Pending", "Under Review"]]})
        approved = frappe.db.count("Adoption Application", {"status": "Approved"})
        completed = frappe.db.count("Adoption Application", {"status": "Adoption Completed"})

        apps = frappe.get_all(
            "Adoption Application",
            filters={"status": ["in", ["Pending", "Under Review"]]},
            fields=["applicant_name", "status", "creation"],
            order_by="creation asc",
            limit=5
        )
        lines = ""
        if apps:
            lines = "\n\nNewest pending:\n" + "\n".join([
                f"• {a.applicant_name} — {a.status}" for a in apps
            ])

        return {
            "reply": (
                f"**Adoption Applications:**\n\n"
                f"• **{pending}** pending/under review\n"
                f"• **{approved}** approved (awaiting pickup)\n"
                f"• **{completed}** completed total"
                f"{lines}"
            ),
            "actions": [
                {"label": "View Pending", "route": "/app/adoption-application?status=Pending"},
                {"label": "View All", "route": "/app/adoption-application"}
            ]
        }

    # --- Recent admissions ---
    if any(k in msg for k in ["recent", "admission", "intake", "new animal", "just arrived"]):
        admissions = frappe.get_all(
            "Animal Admission",
            filters={"docstatus": 1},
            fields=["animal_name_field", "admission_type", "species", "creation"],
            order_by="creation desc",
            limit=5
        )
        if admissions:
            lines = "\n".join([
                f"• **{a.animal_name_field}** ({a.species}) — {a.admission_type} on {str(a.creation)[:10]}"
                for a in admissions
            ])
            return {
                "reply": f"Most recent admissions:\n\n{lines}",
                "actions": [{"label": "View All Admissions", "route": "/app/animal-admission"}]
            }
        return {"reply": "No recent admissions found.", "actions": []}

    # --- Donations ---
    if any(k in msg for k in ["donation", "fundrais", "money", "funds"]):
        first_day = get_first_day(now)
        data = frappe.db.sql(
            """SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt FROM `tabDonation`
            WHERE docstatus = 1 AND donation_date >= %(first_day)s""",
            {"first_day": first_day},
            as_dict=True
        )
        total = flt(data[0].total) if data else 0
        count = cint(data[0].cnt) if data else 0

        return {
            "reply": (
                f"**Donations this month:**\n\n"
                f"• Total received: **R {total:,.0f}**\n"
                f"• Number of donations: **{count}**"
            ),
            "actions": [{"label": "View Donations", "route": "/app/donation"}]
        }

    # --- Daily round ---
    if any(k in msg for k in ["daily round", "morning check", "evening check", "rounds"]):
        today_rounds = frappe.db.count("Daily Round", {"round_date": now})
        return {
            "reply": f"**{today_rounds}** daily round(s) recorded for today.",
            "actions": [
                {"label": "View Today's Rounds", "route": "/app/daily-round?round_date=" + now},
                {"label": "New Round", "route": "/app/daily-round/new"}
            ]
        }

    # --- Volunteers ---
    if any(k in msg for k in ["volunteer", "help", "staff"]):
        active = frappe.db.count("Volunteer", {"status": "Active"})
        return {
            "reply": f"There are currently **{active}** active volunteers registered.",
            "actions": [{"label": "View Volunteers", "route": "/app/volunteer"}]
        }

    # --- Greetings ---
    if any(k in msg for k in ["hello", "hi ", "hey", "good morning", "good afternoon"]):
        user_name = frappe.db.get_value("User", frappe.session.user, "first_name") or "there"
        total = frappe.db.count("Animal", {"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]})
        appts = frappe.db.count("Veterinary Appointment", {"appointment_date": now, "status": ["!=", "Cancelled"]})
        pending = frappe.db.count("Adoption Application", {"status": ["in", ["Pending", "Under Review"]]})

        return {
            "reply": (
                f"Hello {user_name}! 👋 Here's your quick overview:\n\n"
                f"• **{total}** animals in shelter\n"
                f"• **{appts}** vet appointments today\n"
                f"• **{pending}** pending adoption applications\n\n"
                "How can I help you today?"
            ),
            "actions": [{"label": "Open Dashboard", "route": "/app/kennel-dashboard"}]
        }

    # --- Thank you ---
    if any(k in msg for k in ["thank", "thanks", "cheers"]):
        return {"reply": "You're welcome! 😊 Let me know if there's anything else.", "actions": []}

    # --- Long stay animals ---
    if any(k in msg for k in ["long stay", "longest", "been here", "waiting", "stuck", "overdue"]):
        from frappe.utils import add_days as _ad
        cutoff = _ad(now, -30)
        count = frappe.db.count("Animal", {
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            "intake_date": ["<=", cutoff],
        })
        animals = frappe.get_all("Animal", filters={
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            "intake_date": ["<=", cutoff],
        }, fields=["animal_name", "species", "intake_date"], order_by="intake_date asc", limit=5)
        if animals:
            lines = "\n".join([
                f"• **{a.animal_name}** ({a.species}) — since {a.intake_date}" for a in animals
            ])
            return {
                "reply": f"**{count} animals** have been in the shelter for over 30 days:\n\n{lines}",
                "actions": [{"label": "View Long-Stay Animals", "route": "/app/animal?intake_date=%5B%22%3C%3D%22%2C%22" + cutoff + "%22%5D"}]
            }
        return {"reply": "No animals have been here longer than 30 days. Great turnover! 🎉", "actions": []}

    # --- Kennel capacity detail ---
    if any(k in msg for k in ["full kennel", "capacity alert", "overcrowd", "no space"]):
        from frappe.utils import cint as _ci
        data = frappe.db.sql(
            "SELECT SUM(capacity) as cap, SUM(current_occupancy) as occ FROM `tabKennel` WHERE status NOT IN ('Maintenance','Out of Service')",
            as_dict=True
        )
        cap = _ci(data[0].cap) if data else 0
        occ = _ci(data[0].occ) if data else 0
        rate = round(occ / cap * 100) if cap else 0
        full = frappe.get_all("Kennel", filters={"current_occupancy": [">=", frappe.qb.Field("capacity")], "status": ["not in", ["Maintenance", "Out of Service"]]}, fields=["kennel_name"], limit=10)
        full_names = ", ".join(k.kennel_name for k in full) if full else "None"
        level = "🟢 Good" if rate < 80 else "🟡 High" if rate < 95 else "🔴 Critical"
        return {
            "reply": f"**Capacity Status: {level} ({rate}%)**\n\n• Using {occ}/{cap} spaces\n• Full kennels: {full_names}",
            "actions": [{"label": "View Kennels", "route": "/app/kennel"}]
        }

    # --- Which animal is in kennel X ---
    import re
    kennel_lookup = re.search(r"(?:who|which|what).*(?:in|inside|at)\s+(?:kennel\s+)?[\"']?([a-zA-Z0-9\-_ ]+)[\"']?", msg)
    if not kennel_lookup:
        kennel_lookup = re.search(r"kennel\s+[\"']?([a-zA-Z0-9\-_ ]+)[\"']?\s+(?:has|have|contain|hold)", msg)
    if kennel_lookup:
        kennel_query = kennel_lookup.group(1).strip()
        # Try to find kennel by name or ID
        kennel_match = frappe.db.sql(
            """SELECT name, kennel_name FROM `tabKennel`
            WHERE LOWER(kennel_name) LIKE %s OR LOWER(name) LIKE %s
            LIMIT 1""",
            (f"%{kennel_query}%", f"%{kennel_query}%"),
            as_dict=True
        )
        if kennel_match:
            k = kennel_match[0]
            animals = frappe.get_all("Animal", filters={
                "current_kennel": k.name,
                "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            }, fields=["name", "animal_name", "species", "breed", "status", "animal_photo", "gender", "intake_date"])
            if animals:
                lines = "\n".join([
                    f"• **{a.animal_name}** — {a.species}{(' / ' + a.breed) if a.breed else ''} ({a.status})"
                    for a in animals
                ])
                animal_cards = []
                for a in animals:
                    animal_cards.append({
                        "name": a.name,
                        "animal_name": a.animal_name,
                        "species": a.species,
                        "breed": a.breed or "",
                        "status": a.status,
                        "gender": a.gender or "",
                        "photo": a.animal_photo or "",
                        "intake_date": str(a.intake_date or ""),
                    })
                return {
                    "reply": f"**{k.kennel_name}** has **{len(animals)}** animal(s):\n\n{lines}",
                    "animals": animal_cards,
                    "actions": [{"label": f"View {k.kennel_name}", "route": f"/app/kennel/{k.name}"}]
                }
            else:
                return {
                    "reply": f"**{k.kennel_name}** is currently empty.",
                    "actions": [{"label": f"View {k.kennel_name}", "route": f"/app/kennel/{k.name}"}]
                }

    # --- Where is [animal name] / find animal ---
    find_animal = re.search(r"(?:where|find|look\s*up|search|show|which kennel).*?(?:is|for|me)?\s+[\"']?([a-zA-Z][a-zA-Z ]{1,30})[\"']?", msg)
    if not find_animal:
        find_animal = re.search(r"[\"']([a-zA-Z][a-zA-Z ]{1,30})[\"']\s+(?:kennel|location|where)", msg)
    if find_animal:
        animal_query = find_animal.group(1).strip()
        # Skip common non-animal words
        skip_words = {"the", "all", "any", "some", "me", "kennel", "animal", "dog", "cat", "pet",
                      "vet", "shelter", "adoption", "appointment", "donation", "volunteer", "staff",
                      "capacity", "occupancy", "species", "breed", "today", "round", "application"}
        if animal_query.lower() not in skip_words and len(animal_query) > 1:
            animals = frappe.db.sql(
                """SELECT name, animal_name, species, breed, status, current_kennel,
                          animal_photo, gender, intake_date, weight_kg, is_special_needs
                FROM `tabAnimal`
                WHERE LOWER(animal_name) LIKE %s
                AND status NOT IN ('Adopted', 'Transferred', 'Deceased', 'Returned to Owner')
                ORDER BY animal_name ASC LIMIT 5""",
                (f"%{animal_query}%",),
                as_dict=True
            )
            if animals:
                lines = []
                animal_cards = []
                for a in animals:
                    kennel_name = ""
                    if a.current_kennel:
                        kennel_name = frappe.db.get_value("Kennel", a.current_kennel, "kennel_name") or a.current_kennel
                    location = f" in **{kennel_name}**" if kennel_name else " — no kennel assigned"
                    lines.append(f"• **{a.animal_name}** ({a.species}{(' / ' + a.breed) if a.breed else ''}){location} — {a.status}")
                    animal_cards.append({
                        "name": a.name,
                        "animal_name": a.animal_name,
                        "species": a.species,
                        "breed": a.breed or "",
                        "status": a.status,
                        "gender": a.gender or "",
                        "photo": a.animal_photo or "",
                        "kennel": kennel_name,
                        "intake_date": str(a.intake_date or ""),
                        "weight_kg": float(a.weight_kg or 0),
                        "is_special_needs": a.is_special_needs or 0,
                    })
                header = f"Found **{len(animals)}** animal(s) matching \"{animal_query}\":"
                return {
                    "reply": f"{header}\n\n" + "\n".join(lines),
                    "animals": animal_cards,
                    "actions": [{"label": "View All Animals", "route": "/app/animal"}]
                }

    return None


def _try_ai_query(message):
    """Try to answer using an external AI API if configured."""
    try:
        settings = frappe.get_single("Kennel Management Settings")
        if not getattr(settings, "enable_ai_chatbot", False):
            return None

        api_key = getattr(settings, "ai_api_key", None)
        ai_provider = getattr(settings, "ai_provider", None)
        ai_model = getattr(settings, "ai_model", None)
        max_tokens = getattr(settings, "ai_max_tokens", 500) or 500

        if not api_key or not ai_provider:
            return None

        # Build rich shelter context for AI
        from frappe.utils import today, cint, flt, add_days, getdate
        now = today()
        total_animals = frappe.db.count("Animal", {"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]})
        available = frappe.db.count("Animal", {"status": "Available for Adoption"})
        quarantine = frappe.db.count("Animal", {"status": "Quarantine"})
        medical_hold = frappe.db.count("Animal", {"status": "Medical Hold"})
        foster = frappe.db.count("Animal", {"status": "In Foster Care"})
        pending = frappe.db.count("Adoption Application", {"status": ["in", ["Pending", "Under Review"]]})
        appts = frappe.db.count("Veterinary Appointment", {"appointment_date": now, "status": ["!=", "Cancelled"]})

        # Species breakdown
        species_data = frappe.db.sql(
            """SELECT species, COUNT(*) as cnt FROM `tabAnimal`
            WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
            GROUP BY species ORDER BY cnt DESC LIMIT 5""", as_dict=True
        )
        species_str = ", ".join([f"{s.species}: {s.cnt}" for s in species_data]) if species_data else "none"

        # Kennel capacity
        k_data = frappe.db.sql(
            "SELECT SUM(capacity) as cap, SUM(current_occupancy) as occ FROM `tabKennel`", as_dict=True
        )
        k_cap = cint(k_data[0].cap) if k_data else 0
        k_occ = cint(k_data[0].occ) if k_data else 0
        k_rate = round(k_occ / k_cap * 100) if k_cap else 0

        # Recent animals list for name lookup
        recent_animals = frappe.get_all("Animal", filters={
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]
        }, fields=["animal_name", "species", "breed", "current_kennel", "status"], limit=20)
        animal_list_str = "; ".join([
            f"{a.animal_name} ({a.species}{('/' + a.breed) if a.breed else ''}, {a.status}, kennel: {a.current_kennel or 'none'})"
            for a in recent_animals
        ]) if recent_animals else "no animals"

        # Long stay count
        cutoff_30 = add_days(now, -30)
        long_stay = frappe.db.count("Animal", {
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            "intake_date": ["<=", cutoff_30],
        })

        context = (
            f"You are FurEver Assistant, the AI helper for an SPCA animal shelter management system called FurEver. "
            f"Today: {now}. "
            f"SHELTER STATS: {total_animals} animals total ({available} available for adoption, "
            f"{quarantine} in quarantine, {medical_hold} medical hold, {foster} in foster). "
            f"Species: {species_str}. "
            f"Kennel occupancy: {k_occ}/{k_cap} ({k_rate}%). "
            f"{pending} pending adoption applications. {appts} vet appointments today. "
            f"{long_stay} animals in shelter 30+ days. "
            f"CURRENT ANIMALS: {animal_list_str}. "
            f"RULES: Be helpful, concise, friendly. Use **bold** for numbers/names. "
            f"When asked about a specific animal, use the data above. "
            f"Suggest relevant actions like viewing records or scheduling appointments."
        )

        if ai_provider == "OpenAI":
            return _call_openai(api_key, ai_model or "gpt-4o-mini", context, message, max_tokens)
        elif ai_provider == "Anthropic":
            return _call_anthropic(api_key, ai_model or "claude-sonnet-4-20250514", context, message, max_tokens)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Chatbot AI Error")

    return None


def _call_openai(api_key, model, context, message, max_tokens=500):
    """Call OpenAI API."""
    import requests

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": context},
                {"role": "user", "content": message}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        },
        timeout=30
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return {"reply": reply, "actions": []}

    return None


def _call_anthropic(api_key, model, context, message, max_tokens=500):
    """Call Anthropic API."""
    import requests

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": context,
            "messages": [{"role": "user", "content": message}]
        },
        timeout=30
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["content"][0]["text"]
        return {"reply": reply, "actions": []}

    return None


# ─── Internal Messaging ──────────────────────────────────────────────
@frappe.whitelist()
def get_chat_users():
    """Return list of users the current user can message, with last message preview."""
    me = frappe.session.user
    users = frappe.get_all(
        "User",
        filters={
            "enabled": 1,
            "user_type": "System User",
            "name": ["!=", me],
            "name": ["not in", ["Guest", "Administrator"]],
        },
        fields=["name as email", "full_name"],
        order_by="full_name asc",
    )

    for u in users:
        # Latest message between me and this user
        last = frappe.db.sql("""
            SELECT content, creation, owner
            FROM `tabKM Internal Message`
            WHERE (owner = %s AND to_user = %s) OR (owner = %s AND to_user = %s)
            ORDER BY creation DESC LIMIT 1
        """, (me, u.email, u.email, me), as_dict=True)
        if last:
            u["last_message"] = last[0].content[:50]
            u["last_time"] = str(last[0].creation)
        else:
            u["last_message"] = ""
            u["last_time"] = ""

        # Unread count
        u["unread"] = frappe.db.count(
            "KM Internal Message",
            filters={"owner": u.email, "to_user": me, "read": 0},
        )

    # Sort: users with recent messages first
    users.sort(key=lambda u: u.get("last_time") or "", reverse=True)
    return users


@frappe.whitelist()
def get_dm_messages(other_user):
    """Return messages between current user and other_user."""
    me = frappe.session.user
    messages = frappe.db.sql("""
        SELECT name, owner as sender, to_user, content, creation,
               (SELECT full_name FROM `tabUser` WHERE name = m.owner) as sender_name
        FROM `tabKM Internal Message` m
        WHERE (owner = %s AND to_user = %s) OR (owner = %s AND to_user = %s)
        ORDER BY creation ASC
        LIMIT 200
    """, (me, other_user, other_user, me), as_dict=True)

    # Mark received messages as read
    frappe.db.sql("""
        UPDATE `tabKM Internal Message`
        SET `read` = 1
        WHERE owner = %s AND to_user = %s AND `read` = 0
    """, (other_user, me))
    frappe.db.commit()

    return messages


@frappe.whitelist()
def send_dm_message(to_user, content):
    """Send a direct message to another user."""
    if not content or not content.strip():
        frappe.throw(_("Message cannot be empty"))
    if len(content) > 5000:
        frappe.throw(_("Message too long"))

    doc = frappe.get_doc({
        "doctype": "KM Internal Message",
        "to_user": to_user,
        "content": content.strip(),
        "read": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name}


@frappe.whitelist()
def get_unread_count():
    """Return total unread message count for current user."""
    me = frappe.session.user
    return frappe.db.count(
        "KM Internal Message",
        filters={"to_user": me, "read": 0},
    )


# ─── Adoption Compatibility Score ────────────────────────────────────
@frappe.whitelist()
def get_adoption_match_score(application):
    """Calculate compatibility score (0-100) between applicant and animal."""
    app = frappe.get_doc("Adoption Application", application)
    if not app.animal:
        return {"score": 0, "breakdown": [], "summary": "No animal selected."}

    animal = frappe.get_doc("Animal", app.animal)
    score = 0
    breakdown = []

    # 1. Species match (15 pts)
    if app.species_preference:
        if app.species_preference == animal.species:
            score += 15
            breakdown.append({"label": "Species match", "points": 15, "max": 15})
        else:
            breakdown.append({"label": "Species mismatch", "points": 0, "max": 15})
    else:
        score += 15
        breakdown.append({"label": "No species preference (open)", "points": 15, "max": 15})

    # 2. Housing suitability (20 pts)
    housing_pts = 10
    if app.has_yard:
        housing_pts += 5
    if app.yard_fenced:
        housing_pts += 5
    # Larger dogs need yards
    if animal.species == "Dog" and animal.size in ["Large (25-45kg)", "Giant (> 45kg)"]:
        if not app.has_yard:
            housing_pts = max(0, housing_pts - 8)
            breakdown.append({"label": "Large dog needs yard", "points": housing_pts, "max": 20})
        else:
            breakdown.append({"label": "Housing suitable for large dog", "points": housing_pts, "max": 20})
    else:
        breakdown.append({"label": "Housing suitability", "points": housing_pts, "max": 20})
    score += housing_pts

    # 3. Experience level (15 pts)
    exp_pts = 5
    if app.previous_pet_experience and app.previous_pet_experience != "None":
        exp_pts += 5
    if app.years_of_experience and int(app.years_of_experience or 0) >= 3:
        exp_pts += 5
    if animal.is_special_needs and exp_pts < 10:
        exp_pts = max(0, exp_pts - 3)
    breakdown.append({"label": "Experience level", "points": exp_pts, "max": 15})
    score += exp_pts

    # 4. Household compatibility (20 pts)
    house_pts = 10
    if animal.good_with_children == "Yes" or int(app.number_of_children or 0) == 0:
        house_pts += 5
    elif animal.good_with_children == "No" and int(app.number_of_children or 0) > 0:
        house_pts -= 5
    if int(app.number_of_current_pets or 0) > 0:
        if animal.good_with_dogs == "Yes" or animal.good_with_cats == "Yes":
            house_pts += 5
        elif animal.good_with_dogs == "No" and animal.good_with_cats == "No":
            house_pts -= 5
    else:
        house_pts += 5
    house_pts = max(0, min(house_pts, 20))
    breakdown.append({"label": "Household compatibility", "points": house_pts, "max": 20})
    score += house_pts

    # 5. Lifestyle fit (15 pts)
    life_pts = 8
    hours = int(app.hours_away_from_home or 0)
    if hours <= 4:
        life_pts += 7
    elif hours <= 8:
        life_pts += 4
    else:
        life_pts -= 3
    life_pts = max(0, min(life_pts, 15))
    breakdown.append({"label": "Lifestyle fit (time at home)", "points": life_pts, "max": 15})
    score += life_pts

    # 6. Commitment signals (15 pts)
    commit_pts = 0
    if app.commitment_acknowledgement:
        commit_pts += 5
    if not app.has_surrendered_pet_before:
        commit_pts += 5
    if app.vet_name:
        commit_pts += 5
    breakdown.append({"label": "Commitment signals", "points": commit_pts, "max": 15})
    score += commit_pts

    score = min(score, 100)

    if score >= 80:
        summary = "Excellent match! This applicant is highly compatible."
    elif score >= 60:
        summary = "Good match. A few areas could be discussed during the home check."
    elif score >= 40:
        summary = "Moderate match. Review the lower-scoring areas carefully."
    else:
        summary = "Low compatibility. Significant concerns to address before approval."

    return {"score": score, "breakdown": breakdown, "summary": summary}


# ─── Animal Health Summary ───────────────────────────────────────────
@frappe.whitelist()
def get_animal_health_summary(animal):
    """Return health overview for an animal: vaccinations, vet visits, next appointment."""
    from frappe.utils import today, getdate, add_days

    result = {"vaccinations": [], "recent_visits": [], "next_appointment": None, "alerts": []}

    # Vaccination status
    vaccinations = frappe.db.sql("""
        SELECT vi.vaccine_name, vi.vaccination_date, vi.next_due_date, vi.status
        FROM `tabVaccination Item` vi
        INNER JOIN `tabVeterinary Record` vr ON vi.parent = vr.name
        WHERE vr.animal = %s AND vr.docstatus = 1
        ORDER BY vi.vaccination_date DESC
    """, animal, as_dict=True)

    for v in vaccinations:
        if v.next_due_date and getdate(v.next_due_date) < getdate(today()):
            v["alert"] = "overdue"
            result["alerts"].append("Vaccination '{}' is overdue since {}".format(v.vaccine_name, v.next_due_date))
        elif v.next_due_date and getdate(v.next_due_date) <= getdate(add_days(today(), 14)):
            v["alert"] = "due_soon"
        else:
            v["alert"] = "ok"

    result["vaccinations"] = vaccinations[:10]

    # Recent vet visits
    result["recent_visits"] = frappe.get_all(
        "Veterinary Appointment",
        filters={"animal": animal, "status": "Completed"},
        fields=["name", "appointment_date", "appointment_type", "veterinarian", "diagnosis"],
        order_by="appointment_date desc",
        limit=5,
    )

    # Next upcoming appointment
    upcoming = frappe.get_all(
        "Veterinary Appointment",
        filters={"animal": animal, "status": "Scheduled", "appointment_date": [">=", today()]},
        fields=["name", "appointment_date", "appointment_type", "veterinarian", "appointment_time"],
        order_by="appointment_date asc",
        limit=1,
    )
    if upcoming:
        result["next_appointment"] = upcoming[0]

    # Days in shelter
    intake = frappe.db.get_value("Animal", animal, "intake_date")
    if intake:
        result["days_in_shelter"] = (getdate(today()) - getdate(intake)).days
    else:
        result["days_in_shelter"] = 0

    # Weight history
    weights = frappe.db.sql("""
        SELECT appointment_date, weight_kg
        FROM `tabVeterinary Appointment`
        WHERE animal = %s AND weight_kg > 0 AND status = 'Completed'
        ORDER BY appointment_date ASC
    """, animal, as_dict=True)
    result["weight_history"] = weights

    return result


# ─── Long-Stay Animals ───────────────────────────────────────────────
@frappe.whitelist()
def get_long_stay_animals(threshold_days=30):
    """Return animals that have been in the shelter longer than threshold_days."""
    from frappe.utils import today, add_days

    threshold_days = int(threshold_days)
    cutoff = add_days(today(), -threshold_days)
    animals = frappe.get_all(
        "Animal",
        filters={
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            "intake_date": ["<=", cutoff],
        },
        fields=["name", "animal_name", "species", "breed", "intake_date", "status", "current_kennel", "animal_photo"],
        order_by="intake_date asc",
    )
    for a in animals:
        a["days"] = (getdate(today()) - getdate(a.intake_date)).days
    return animals


# ─── Smart Kennel Assignment ─────────────────────────────────────────
@frappe.whitelist()
def get_kennel_recommendations(animal):
    """Suggest best kennels for an animal based on species, size, needs."""
    animal_doc = frappe.get_doc("Animal", animal)
    needs_quarantine = animal_doc.status == "Quarantine"
    needs_isolation = animal_doc.status in ["Medical Hold", "In Treatment"]
    is_small = animal_doc.size in ["Tiny (< 5kg)", "Small (5-10kg)"]
    is_large = animal_doc.size in ["Large (25-45kg)", "Giant (> 45kg)"]

    kennels = frappe.get_all(
        "Kennel",
        filters={"status": ["in", ["Available", "Occupied"]]},
        fields=["name", "kennel_name", "capacity", "current_occupancy", "kennel_type",
                "size_category", "is_quarantine", "is_isolation",
                "has_outdoor_access", "has_heating", "has_cooling"],
    )

    scored = []
    for k in kennels:
        if k.current_occupancy >= k.capacity:
            continue
        s = 50
        # Quarantine matching
        if needs_quarantine and k.is_quarantine:
            s += 30
        elif needs_quarantine and not k.is_quarantine:
            continue
        elif not needs_quarantine and k.is_quarantine:
            continue
        # Isolation matching
        if needs_isolation and k.is_isolation:
            s += 20
        elif needs_isolation and not k.is_isolation:
            s -= 10
        # Size matching
        if is_large and k.size_category in ["Large", "Extra Large"]:
            s += 15
        elif is_small and k.size_category in ["Small", "Medium"]:
            s += 15
        elif is_large and k.size_category == "Small":
            s -= 20
        # Prefer emptier kennels
        occupancy_ratio = k.current_occupancy / k.capacity if k.capacity else 1
        s += int((1 - occupancy_ratio) * 15)
        # Outdoor access bonus for dogs
        if animal_doc.species == "Dog" and k.has_outdoor_access:
            s += 10
        k["score"] = max(0, min(s, 100))
        k["available_spots"] = k.capacity - k.current_occupancy
        scored.append(k)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:5]


# ─── Auto Daily Rounds ───────────────────────────────────────────────
@frappe.whitelist()
def generate_daily_rounds():
    """Auto-generate daily round entries for all occupied kennels."""
    from frappe.utils import today

    occupied_kennels = frappe.get_all(
        "Kennel",
        filters={"status": "Occupied", "current_occupancy": [">", 0]},
        fields=["name", "kennel_name"],
    )

    created = 0
    for kennel in occupied_kennels:
        # Check if already created for today
        existing = frappe.db.exists("Daily Round", {
            "round_date": today(),
            "kennel": kennel.name,
        })
        if existing:
            continue

        animals = frappe.get_all(
            "Animal",
            filters={
                "current_kennel": kennel.name,
                "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            },
            fields=["name", "animal_name"],
        )

        if not animals:
            continue

        doc = frappe.get_doc({
            "doctype": "Daily Round",
            "round_date": today(),
            "kennel": kennel.name,
            "status": "Draft",
        })
        # Add detail rows for each animal
        for animal in animals:
            doc.append("details", {
                "animal": animal.name,
                "animal_name": animal.animal_name,
            })
        doc.insert(ignore_permissions=True)
        created += 1

    frappe.db.commit()
    return {"created": created, "total_kennels": len(occupied_kennels)}


# ─── Kennel Capacity Overview ────────────────────────────────────────
@frappe.whitelist()
def get_kennel_capacity_overview():
    """Return kennel capacity overview with alerts for near-full or full kennels."""
    kennels = frappe.get_all(
        "Kennel",
        fields=["name", "kennel_name", "capacity", "current_occupancy", "status",
                "kennel_type", "size_category", "is_quarantine", "is_isolation"],
        order_by="kennel_name asc",
    )
    total_capacity = 0
    total_occupancy = 0
    alerts = []
    for k in kennels:
        total_capacity += (k.capacity or 0)
        total_occupancy += (k.current_occupancy or 0)
        k["utilization"] = round((k.current_occupancy / k.capacity * 100), 1) if k.capacity else 0
        if k.current_occupancy >= k.capacity and k.status not in ["Maintenance", "Out of Service"]:
            alerts.append("{} is FULL ({}/{})".format(k.kennel_name, k.current_occupancy, k.capacity))
        elif k.capacity and k.current_occupancy / k.capacity >= 0.8:
            alerts.append("{} is nearly full ({}/{})".format(k.kennel_name, k.current_occupancy, k.capacity))

    overall = round((total_occupancy / total_capacity * 100), 1) if total_capacity else 0
    return {
        "kennels": kennels,
        "total_capacity": total_capacity,
        "total_occupancy": total_occupancy,
        "overall_utilization": overall,
        "alerts": alerts,
    }


# ─── Voice/Video Call Signaling ──────────────────────────────────────
@frappe.whitelist()
def initiate_call(to_user, call_type="voice"):
    """Send a call invitation to another user via Frappe realtime."""
    if call_type not in ("voice", "video"):
        frappe.throw(_("Invalid call type"))

    me = frappe.session.user
    my_name = frappe.db.get_value("User", me, "full_name") or me

    call_id = frappe.generate_hash(length=12)

    # Notify the recipient via realtime
    frappe.publish_realtime(
        event="km_incoming_call",
        message={
            "call_id": call_id,
            "from_user": me,
            "from_name": my_name,
            "call_type": call_type,
        },
        user=to_user,
    )

    return {"call_id": call_id, "call_type": call_type}


@frappe.whitelist()
def call_signal(to_user, call_id, signal_type, payload=None):
    """Relay WebRTC signaling messages (offer/answer/ice-candidate/end)."""
    valid_signals = ("offer", "answer", "ice-candidate", "call-end", "call-reject", "call-accept")
    if signal_type not in valid_signals:
        frappe.throw(_("Invalid signal type"))

    me = frappe.session.user
    my_name = frappe.db.get_value("User", me, "full_name") or me

    frappe.publish_realtime(
        event="km_call_signal",
        message={
            "call_id": call_id,
            "signal_type": signal_type,
            "from_user": me,
            "from_name": my_name,
            "payload": frappe.parse_json(payload) if isinstance(payload, str) else payload,
        },
        user=to_user,
    )

    return {"ok": True}


# ─── Animal Lookup for Chatbot ───────────────────────────────────────
@frappe.whitelist()
def get_animal_detail(animal):
    """Return detailed animal info with photo for chatbot cards."""
    doc = frappe.get_doc("Animal", animal)
    kennel_name = ""
    if doc.current_kennel:
        kennel_name = frappe.db.get_value("Kennel", doc.current_kennel, "kennel_name") or doc.current_kennel

    return {
        "name": doc.name,
        "animal_name": doc.animal_name,
        "species": doc.species,
        "breed": doc.breed or "",
        "status": doc.status,
        "gender": doc.gender or "",
        "photo": doc.animal_photo or "",
        "kennel": kennel_name,
        "kennel_id": doc.current_kennel or "",
        "intake_date": str(doc.intake_date or ""),
        "weight_kg": float(doc.weight_kg or 0),
        "is_special_needs": doc.is_special_needs or 0,
        "date_of_birth": str(doc.date_of_birth or ""),
    }


@frappe.whitelist()
def generate_feeding_round(shift=None):
    """Auto-generate a Feeding Round with all active shelter animals.
    
    Args:
        shift: 'Morning (7:00 AM)' or 'Afternoon (3:00 PM)'
    
    Returns:
        dict with created round name and animal count
    """
    from frappe.utils import today

    if not shift:
        from frappe.utils import nowtime
        hour = int(nowtime().split(":")[0])
        shift = "Morning (7:00 AM)" if hour < 12 else "Afternoon (3:00 PM)"

    # Check if a round already exists for today and this shift
    existing = frappe.db.exists("Feeding Round", {
        "date": today(),
        "shift": shift,
        "docstatus": ["!=", 2],
    })
    if existing:
        return {"message": _("Feeding Round already exists for {0} on {1}").format(shift, today()), "name": existing}

    # Get all active animals in the shelter
    animals = frappe.get_all(
        "Animal",
        filters={
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner", "Lost"]],
        },
        fields=["name", "animal_name", "current_kennel", "species"],
        order_by="current_kennel asc, animal_name asc",
    )

    if not animals:
        return {"message": _("No active animals found in the shelter")}

    # Create the Feeding Round
    feeding_round = frappe.new_doc("Feeding Round")
    feeding_round.date = today()
    feeding_round.shift = shift
    feeding_round.status = "Draft"

    for animal in animals:
        # Lookup active Feeding Schedule for food details
        schedule = frappe.db.get_value(
            "Feeding Schedule",
            {"animal": animal.name, "status": "Active"},
            ["food_type", "quantity_per_meal", "quantity_unit", "special_diet", "allergies"],
            as_dict=True,
        )

        row = feeding_round.append("animals", {})
        row.animal = animal.name
        row.animal_name = animal.animal_name
        row.kennel = animal.current_kennel
        row.species = animal.species
        if schedule:
            row.food_type = schedule.food_type
            row.quantity = schedule.quantity_per_meal
            row.quantity_unit = schedule.quantity_unit
            row.special_diet = schedule.special_diet or 0
            row.allergies = schedule.allergies

    feeding_round.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "message": _("Feeding Round created successfully"),
        "name": feeding_round.name,
        "total_animals": len(animals),
        "shift": shift,
    }


@frappe.whitelist()
def check_overdue_feeding(shift=None):
    """Check for incomplete feeding rounds and send overdue notifications.
    
    Called 1 hour after each feeding time (8 AM for morning, 4 PM for afternoon).
    """
    from frappe.utils import today

    if not shift:
        from frappe.utils import nowtime
        hour = int(nowtime().split(":")[0])
        shift = "Morning (7:00 AM)" if hour < 12 else "Afternoon (3:00 PM)"

    # Find today's feeding round for this shift that isn't completed
    rounds = frappe.get_all(
        "Feeding Round",
        filters={
            "date": today(),
            "shift": shift,
            "docstatus": 0,
            "status": ["!=", "Completed"],
        },
        fields=["name", "total_animals", "animals_fed", "animals_unfed"],
    )

    for rnd in rounds:
        # Mark as overdue
        frappe.db.set_value("Feeding Round", rnd.name, "status", "Overdue")

        unfed_count = rnd.animals_unfed or (rnd.total_animals - (rnd.animals_fed or 0))
        total = rnd.total_animals or 0

        # Get unfed animal names
        unfed_animals = frappe.get_all(
            "Feeding Round Detail",
            filters={"parent": rnd.name, "fed": 0},
            fields=["animal_name", "animal", "kennel"],
            limit=15,
        )
        unfed_names = [a.animal_name or a.animal for a in unfed_animals]

        # Send realtime notification
        frappe.publish_realtime("feeding_overdue", {
            "title": _("Overdue Feeding Alert - {0}").format(shift),
            "message": _(
                "{0} of {1} animals have NOT been fed! "
                "Feeding was due at {2}. Unfed: {3}"
            ).format(
                unfed_count, total,
                "7:00 AM" if "Morning" in shift else "3:00 PM",
                ", ".join(unfed_names[:10]),
            ),
            "round": rnd.name,
            "unfed_count": unfed_count,
            "total": total,
        })

        # Create urgent ToDo
        existing_todo = frappe.db.exists("ToDo", {
            "reference_type": "Feeding Round",
            "reference_name": rnd.name,
            "status": "Open",
        })
        if not existing_todo:
            frappe.get_doc({
                "doctype": "ToDo",
                "description": _(
                    "🚨 OVERDUE FEEDING: {0} animal(s) not fed during {1} round ({2}). "
                    "Unfed animals: {3}"
                ).format(unfed_count, shift, rnd.name, ", ".join(unfed_names[:10])),
                "reference_type": "Feeding Round",
                "reference_name": rnd.name,
                "priority": "Urgent",
                "date": today(),
            }).insert(ignore_permissions=True)

        frappe.db.commit()

    return {"checked": len(rounds), "shift": shift}
