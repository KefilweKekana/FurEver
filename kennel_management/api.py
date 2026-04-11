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
def chatbot_query(message, is_voice=0, conversation_history=None):
    """Process chatbot queries — AI-first with built-in data fallback."""
    from frappe.utils import today, getdate, add_days, get_first_day, flt, cint
    import json as json_mod

    message_lower = (message or "").strip().lower()
    now = today()
    voice_mode = cint(is_voice)

    # Parse conversation history
    history = []
    if conversation_history:
        try:
            history = json_mod.loads(conversation_history) if isinstance(conversation_history, str) else conversation_history
            if not isinstance(history, list):
                history = []
        except (json_mod.JSONDecodeError, TypeError):
            history = []

    # Always try AI first — it has full shelter data + conversation context + reasoning
    ai_reply = _try_ai_query(message, voice_mode=voice_mode, conversation_history=history)
    if ai_reply:
        return ai_reply

    # Fall back to built-in intent matching if AI is not configured or fails
    result = _match_intent(message_lower, now)
    if result:
        return result

    # Final fallback
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


def _try_ai_query(message, voice_mode=0, conversation_history=None):
    """Try to answer using an external AI API if configured.

    Builds a comprehensive system prompt giving the AI full knowledge of
    every doctype, live shelter data, and the ability to answer any question
    about the kennel management system accurately. Sends full conversation
    history for multi-turn context.
    """
    try:
        settings = frappe.get_single("Kennel Management Settings")
        if not getattr(settings, "enable_ai_chatbot", False):
            return None

        api_key = settings.get_password("ai_api_key") if settings.ai_api_key else None
        ai_provider = getattr(settings, "ai_provider", None)
        ai_model = getattr(settings, "ai_model", None)
        max_tokens = getattr(settings, "ai_max_tokens", 4096) or 4096
        temperature = getattr(settings, "ai_temperature", 0.4) or 0.4

        # In voice mode, keep responses conversational but still smart
        if voice_mode:
            max_tokens = min(max_tokens, 600)

        if ai_provider != "Ollama (Local)" and not api_key:
            return None
        if not ai_provider:
            return None

        context = _build_ai_context(settings, message, voice_mode=voice_mode)

        # Use custom system prompt if configured — prepend it
        custom_prompt = getattr(settings, "ai_system_prompt", None)
        if custom_prompt:
            context = custom_prompt + "\n\n" + context

        # Build conversation messages (history + current message)
        history = conversation_history or []

        default_models = {
            "OpenAI": "gpt-4o",
            "Anthropic": "claude-sonnet-4-20250514",
            "Google Gemini": "gemini-2.5-flash",
            "Groq": "llama-3.3-70b-versatile",
            "Mistral": "mistral-large-latest",
            "DeepSeek": "deepseek-chat",
            "Ollama (Local)": "llama3.2",
        }
        model = ai_model or default_models.get(ai_provider, "")

        if ai_provider == "OpenAI":
            return _call_openai(api_key, model, context, message, max_tokens, temperature, history)
        elif ai_provider == "Anthropic":
            return _call_anthropic(api_key, model, context, message, max_tokens, temperature, history)
        elif ai_provider == "Google Gemini":
            return _call_gemini(api_key, model, context, message, max_tokens, temperature, history)
        elif ai_provider == "Groq":
            return _call_groq(api_key, model, context, message, max_tokens, temperature, history)
        elif ai_provider == "Mistral":
            return _call_mistral(api_key, model, context, message, max_tokens, temperature, history)
        elif ai_provider == "DeepSeek":
            return _call_deepseek(api_key, model, context, message, max_tokens, temperature, history)
        elif ai_provider == "Ollama (Local)":
            return _call_ollama(model, context, message, max_tokens, temperature, history)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Chatbot AI Error")

    return None


def _build_ai_context(settings, message, voice_mode=0):
    """Build a comprehensive AI context with full module knowledge and live data."""
    from frappe.utils import today, cint, flt, add_days, getdate, now_datetime, get_first_day

    now = today()
    now_dt = now_datetime()
    animal_limit = 0  # No limit — load ALL animals for maximum intelligence
    shelter_name = getattr(settings, "shelter_name", "SPCA") or "SPCA"

    # ── LIVE SHELTER STATISTICS ──────────────────────────────
    total_animals = frappe.db.count("Animal", {"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]})
    status_counts = frappe.db.sql(
        """SELECT status, COUNT(*) as cnt FROM `tabAnimal`
        WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
        GROUP BY status ORDER BY cnt DESC""", as_dict=True
    )
    status_str = ", ".join([f"{s.status}: {s.cnt}" for s in status_counts]) if status_counts else "none"

    species_data = frappe.db.sql(
        """SELECT species, COUNT(*) as cnt FROM `tabAnimal`
        WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
        GROUP BY species ORDER BY cnt DESC""", as_dict=True
    )
    species_str = ", ".join([f"{s.species}: {s.cnt}" for s in species_data]) if species_data else "none"

    # Kennel data
    k_data = frappe.db.sql(
        "SELECT SUM(capacity) as cap, SUM(current_occupancy) as occ FROM `tabKennel`", as_dict=True
    )
    k_cap = cint(k_data[0].cap) if k_data else 0
    k_occ = cint(k_data[0].occ) if k_data else 0
    k_rate = round(k_occ / k_cap * 100) if k_cap else 0
    avail_kennels = frappe.db.count("Kennel", {"status": "Available"})
    full_kennels = frappe.db.sql(
        "SELECT kennel_name FROM `tabKennel` WHERE current_occupancy >= capacity AND status NOT IN ('Maintenance','Out of Service') LIMIT 10",
        as_dict=True
    )
    full_kennel_names = ", ".join([k.kennel_name for k in full_kennels]) if full_kennels else "none"

    # All kennels with occupancy
    all_kennels = frappe.db.sql(
        """SELECT kennel_name, kennel_type, section, capacity, current_occupancy, status
        FROM `tabKennel` ORDER BY kennel_name""", as_dict=True
    )
    kennel_detail_lines = []
    for k in all_kennels:
        kennel_detail_lines.append(f"  {k.kennel_name} ({k.kennel_type}): {k.current_occupancy}/{k.capacity} — {k.status}" + (f" [section: {k.section}]" if k.section else ""))
    kennel_detail_str = "\n".join(kennel_detail_lines) if kennel_detail_lines else "  No kennels configured"

    # Pending adoptions
    pending_adoptions = frappe.db.count("Adoption Application", {"status": ["in", ["Pending", "Under Review"]]})
    approved_adoptions = frappe.db.count("Adoption Application", {"status": "Approved"})
    completed_adoptions = frappe.db.count("Adoption Application", {"status": "Adoption Completed"})

    # Today's vet appointments
    vet_today = frappe.get_all(
        "Veterinary Appointment",
        filters={"appointment_date": now, "status": ["!=", "Cancelled"]},
        fields=["animal_name", "appointment_type", "appointment_time", "status", "veterinarian", "priority"],
        order_by="appointment_time asc",
        limit=20
    )
    vet_lines = []
    for a in vet_today:
        time_str = str(a.appointment_time or "")[:5] or "--:--"
        vet_lines.append(f"  {time_str} — {a.animal_name}: {a.appointment_type} ({a.status}, {a.priority})")
    vet_str = "\n".join(vet_lines) if vet_lines else "  None scheduled"

    # Upcoming vet appointments (next 7 days)
    upcoming_vet = frappe.db.sql(
        """SELECT appointment_date, animal_name, appointment_type, status
        FROM `tabVeterinary Appointment`
        WHERE appointment_date > %s AND appointment_date <= %s AND status != 'Cancelled'
        ORDER BY appointment_date, appointment_time LIMIT 15""",
        (now, add_days(now, 7)), as_dict=True
    )
    upcoming_vet_lines = []
    for a in upcoming_vet:
        upcoming_vet_lines.append(f"  {a.appointment_date} — {a.animal_name}: {a.appointment_type} ({a.status})")
    upcoming_vet_str = "\n".join(upcoming_vet_lines) if upcoming_vet_lines else "  None"

    # Today's feeding rounds
    feeding_today = frappe.get_all(
        "Feeding Round",
        filters={"date": now},
        fields=["shift", "status", "assigned_to", "total_animals", "animals_fed", "completion_percentage"],
        order_by="shift asc"
    )
    feeding_lines = []
    for f in feeding_today:
        feeding_lines.append(f"  {f.shift}: {f.status} — {f.animals_fed}/{f.total_animals} fed ({flt(f.completion_percentage):.0f}%)")
    feeding_str = "\n".join(feeding_lines) if feeding_lines else "  No feeding rounds today"

    # Today's daily rounds
    rounds_today = frappe.db.count("Daily Round", {"round_date": now} if frappe.db.has_column("Daily Round", "round_date") else {"date": now})

    # Donations this month
    first_day = get_first_day(now)
    donation_data = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt FROM `tabDonation`
        WHERE docstatus = 1 AND donation_date >= %s""",
        first_day, as_dict=True
    )
    donation_total = flt(donation_data[0].total) if donation_data else 0
    donation_count = cint(donation_data[0].cnt) if donation_data else 0

    # Volunteers
    active_volunteers = frappe.db.count("Volunteer", {"status": "Active"})

    # Long-stay animals (30+ days)
    cutoff_30 = add_days(now, -30)
    long_stay_count = frappe.db.count("Animal", {
        "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
        "intake_date": ["<=", cutoff_30],
    })

    # Active boarding
    active_boarding = frappe.db.count("Boarding Animal Form", {"status": "Active", "docstatus": 1})

    # Lost & found open cases
    open_lost = frappe.db.count("Lost and Found Report", {"status": ["in", ["Open", "Investigating"]], "report_type": "Lost"})
    open_found = frappe.db.count("Lost and Found Report", {"status": ["in", ["Open", "Investigating"]], "report_type": "Found"})

    # Pending foster applications
    pending_foster = frappe.db.count("Foster Application", {"status": "Pending"})
    active_foster = frappe.db.count("Foster Application", {"status": "Active"})

    # Recent admissions (last 7 days)
    recent_admissions = frappe.get_all(
        "Animal Admission",
        filters={"docstatus": 1, "admission_date": [">=", add_days(now, -7)]},
        fields=["animal_name_field", "species", "breed", "admission_type", "condition_on_arrival", "admission_date"],
        order_by="admission_date desc",
        limit=10
    )
    admission_lines = []
    for a in recent_admissions:
        admission_lines.append(f"  {str(a.admission_date)[:10]} — {a.animal_name_field} ({a.species}{('/' + a.breed) if a.breed else ''}): {a.admission_type}, condition: {a.condition_on_arrival}")
    admission_str = "\n".join(admission_lines) if admission_lines else "  None in last 7 days"

    # Recent adoptions (last 30 days)
    recent_adoptions = frappe.db.sql(
        """SELECT applicant_name, animal_name, adoption_date, species_preference
        FROM `tabAdoption Application`
        WHERE status = 'Adoption Completed' AND adoption_date >= %s
        ORDER BY adoption_date DESC LIMIT 10""",
        add_days(now, -30), as_dict=True
    )
    adoption_lines = []
    for a in recent_adoptions:
        adoption_lines.append(f"  {a.adoption_date} — {a.animal_name or 'N/A'} adopted by {a.applicant_name}")
    adoption_str = "\n".join(adoption_lines) if adoption_lines else "  None in last 30 days"

    # ── FULL ANIMAL ROSTER ───────────────────────────────────
    all_animals = frappe.get_all("Animal", filters={
        "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]
    }, fields=[
        "name", "animal_name", "species", "breed", "gender", "status",
        "current_kennel", "intake_date", "weight_kg", "estimated_age_years",
        "estimated_age_months", "temperament", "spay_neuter_status", "is_special_needs",
        "microchip_number", "color", "size", "energy_level",
        "good_with_dogs", "good_with_cats", "good_with_children",
    ], order_by="animal_name asc", limit_page_length=0)

    animal_roster_lines = []
    for a in all_animals:
        kennel_name = ""
        if a.current_kennel:
            kennel_name = frappe.db.get_value("Kennel", a.current_kennel, "kennel_name") or a.current_kennel
        age_str = ""
        if a.estimated_age_years:
            age_str = f"{a.estimated_age_years}y"
            if a.estimated_age_months:
                age_str += f"{a.estimated_age_months}m"
        elif a.estimated_age_months:
            age_str = f"{a.estimated_age_months}m"

        parts = [
            f"  {a.name} | {a.animal_name}",
            f"species={a.species}",
            f"breed={a.breed or '?'}",
            f"gender={a.gender or '?'}",
            f"status={a.status}",
        ]
        if kennel_name:
            parts.append(f"kennel={kennel_name}")
        if age_str:
            parts.append(f"age={age_str}")
        if a.weight_kg:
            parts.append(f"weight={a.weight_kg}kg")
        if a.color:
            parts.append(f"color={a.color}")
        if a.size:
            parts.append(f"size={a.size}")
        if a.temperament:
            parts.append(f"temperament={a.temperament}")
        if a.spay_neuter_status and a.spay_neuter_status != "Intact":
            parts.append(f"fixed={a.spay_neuter_status}")
        if a.is_special_needs:
            parts.append("SPECIAL_NEEDS")
        if a.microchip_number:
            parts.append(f"chip={a.microchip_number}")
        if a.energy_level:
            parts.append(f"energy={a.energy_level}")
        if a.good_with_dogs and a.good_with_dogs != "Unknown":
            parts.append(f"dogs={a.good_with_dogs}")
        if a.good_with_cats and a.good_with_cats != "Unknown":
            parts.append(f"cats={a.good_with_cats}")
        if a.good_with_children and a.good_with_children != "Unknown":
            parts.append(f"kids={a.good_with_children}")
        if a.intake_date:
            parts.append(f"since={a.intake_date}")

        animal_roster_lines.append(" | ".join(parts))

    animal_roster = "\n".join(animal_roster_lines) if animal_roster_lines else "  No animals currently in shelter"

    # ── PENDING ADOPTION APPLICATIONS ────────────────────────
    pending_apps = frappe.get_all("Adoption Application",
        filters={"status": ["in", ["Pending", "Under Review"]]},
        fields=["name", "applicant_name", "animal_name", "status", "application_date", "species_preference"],
        order_by="application_date asc", limit=15
    )
    pending_app_lines = []
    for a in pending_apps:
        pending_app_lines.append(f"  {a.name} | {a.applicant_name} → {a.animal_name or a.species_preference or 'any'} ({a.status}, applied {a.application_date})")
    pending_app_str = "\n".join(pending_app_lines) if pending_app_lines else "  None"

    # ── VETERINARY RECORDS (recent 30 days) ──────────────────
    recent_vet_records = frappe.db.sql(
        """SELECT vr.animal_name, vr.date, vr.record_type, vr.veterinarian,
                  vr.description, vr.treatment
           FROM `tabVeterinary Record` vr
           WHERE vr.date >= %s
           ORDER BY vr.date DESC LIMIT 30""",
        add_days(now, -30), as_dict=True
    )
    vet_record_lines = []
    for v in recent_vet_records:
        desc_short = (v.description or "")[:120].replace("\n", " ")
        treat_short = (v.treatment or "")[:120].replace("\n", " ")
        vet_record_lines.append(
            f"  {v.date} | {v.animal_name} | {v.record_type} | vet: {v.veterinarian or '?'}"
            + (f" | {desc_short}" if desc_short else "")
            + (f" | Tx: {treat_short}" if treat_short else "")
        )
    vet_records_str = "\n".join(vet_record_lines) if vet_record_lines else "  None in last 30 days"

    # ── VACCINATION STATUS ───────────────────────────────────
    vaccination_data = frappe.db.sql(
        """SELECT vi.parent, vi.vaccine_name, vi.date_administered, vi.next_due_date,
                  vr.animal_name
           FROM `tabVaccination Item` vi
           JOIN `tabVeterinary Record` vr ON vi.parent = vr.name
           WHERE vi.date_administered >= %s
           ORDER BY vi.date_administered DESC LIMIT 40""",
        add_days(now, -90), as_dict=True
    )
    vacc_lines = []
    for v in vaccination_data:
        due = f" (next due: {v.next_due_date})" if v.next_due_date else ""
        vacc_lines.append(f"  {v.animal_name} | {v.vaccine_name} on {v.date_administered}{due}")
    vacc_str = "\n".join(vacc_lines) if vacc_lines else "  No vaccinations in last 90 days"

    # Overdue vaccinations
    overdue_vacc = frappe.db.sql(
        """SELECT vi.vaccine_name, vi.next_due_date, vr.animal_name
           FROM `tabVaccination Item` vi
           JOIN `tabVeterinary Record` vr ON vi.parent = vr.name
           WHERE vi.next_due_date IS NOT NULL AND vi.next_due_date < %s
           AND vr.animal_name IN (
               SELECT animal_name FROM `tabAnimal`
               WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner')
           )
           ORDER BY vi.next_due_date ASC LIMIT 20""",
        now, as_dict=True
    )
    overdue_vacc_lines = []
    for v in overdue_vacc:
        overdue_vacc_lines.append(f"  ⚠️ {v.animal_name} | {v.vaccine_name} was due {v.next_due_date}")
    overdue_vacc_str = "\n".join(overdue_vacc_lines) if overdue_vacc_lines else "  None overdue"

    # ── BEHAVIOR ASSESSMENTS ─────────────────────────────────
    behavior_data = frappe.get_all("Behavior Assessment",
        filters={},
        fields=["animal", "assessment_date", "assessor", "overall_temperament",
                "approach_response", "handling_tolerance", "dog_sociability", "cat_sociability",
                "stranger_reaction", "child_reaction", "resource_guarding", "food_guarding",
                "leash_behavior", "energy_level", "aggression_score", "fear_score",
                "sociability_score", "trainability_score"],
        order_by="assessment_date desc",
        limit=30
    )
    behavior_lines = []
    for b in behavior_data:
        animal_name = frappe.db.get_value("Animal", b.animal, "animal_name") or b.animal or "?"
        scores = []
        if b.aggression_score: scores.append(f"aggr:{b.aggression_score}/5")
        if b.fear_score: scores.append(f"fear:{b.fear_score}/5")
        if b.sociability_score: scores.append(f"social:{b.sociability_score}/5")
        if b.trainability_score: scores.append(f"train:{b.trainability_score}/5")
        score_str = " | ".join(scores) if scores else ""
        traits = []
        if b.overall_temperament: traits.append(f"temperament={b.overall_temperament}")
        if b.approach_response: traits.append(f"approach={b.approach_response}")
        if b.handling_tolerance: traits.append(f"handling={b.handling_tolerance}")
        if b.dog_sociability: traits.append(f"dogs={b.dog_sociability}")
        if b.cat_sociability: traits.append(f"cats={b.cat_sociability}")
        if b.child_reaction: traits.append(f"children={b.child_reaction}")
        if b.resource_guarding: traits.append(f"resource_guard={b.resource_guarding}")
        if b.energy_level: traits.append(f"energy={b.energy_level}")
        if b.leash_behavior: traits.append(f"leash={b.leash_behavior}")
        behavior_lines.append(
            f"  {animal_name} ({b.assessment_date}) | {' | '.join(traits)}"
            + (f" | SCORES: {score_str}" if score_str else "")
        )
    behavior_str = "\n".join(behavior_lines) if behavior_lines else "  No behavior assessments on file"

    # ── ACTIVE MEDICATIONS ───────────────────────────────────
    medication_data = frappe.db.sql(
        """SELECT mi.medication_name, mi.dosage, mi.frequency, mi.start_date, mi.end_date,
                  vr.animal_name
           FROM `tabMedication Item` mi
           JOIN `tabVeterinary Record` vr ON mi.parent = vr.name
           WHERE (mi.end_date IS NULL OR mi.end_date >= %s)
           AND mi.start_date IS NOT NULL
           ORDER BY mi.start_date DESC LIMIT 30""",
        now, as_dict=True
    )
    med_lines = []
    for m in medication_data:
        end = f" until {m.end_date}" if m.end_date else " (ongoing)"
        med_lines.append(
            f"  {m.animal_name} | {m.medication_name} {m.dosage or ''} {m.frequency or ''}{end}"
        )
    med_str = "\n".join(med_lines) if med_lines else "  No active medications"

    # ── LOST & FOUND DETAILS ─────────────────────────────────
    lost_found_open = frappe.get_all("Lost and Found Report",
        filters={"status": ["in", ["Open", "Investigating"]]},
        fields=["name", "report_type", "reporter_name", "species", "breed", "color",
                "last_seen_location", "last_seen_date", "status", "matched_animal"],
        order_by="creation desc", limit=15
    )
    lf_lines = []
    for lf in lost_found_open:
        desc = f"{lf.species or '?'}"
        if lf.breed: desc += f"/{lf.breed}"
        if lf.color: desc += f", {lf.color}"
        loc = f" at {lf.last_seen_location}" if lf.last_seen_location else ""
        date = f" on {lf.last_seen_date}" if lf.last_seen_date else ""
        matched = f" → MATCHED: {lf.matched_animal}" if lf.matched_animal else ""
        lf_lines.append(f"  {lf.name} | {lf.report_type} | {desc}{loc}{date} | reporter: {lf.reporter_name} ({lf.status}){matched}")
    lf_str = "\n".join(lf_lines) if lf_lines else "  No open cases"

    # ── ACTIVE BOARDING ──────────────────────────────────────
    boarding_data = frappe.get_all("Boarding Animal Form",
        filters={"status": "Active", "docstatus": 1},
        fields=["name", "owner_name_and_surname", "cell_number", "date_in", "date_out",
                "cost_per_day", "total_cost", "amount_paid", "outstanding"],
        order_by="date_in desc", limit=10
    )
    boarding_lines = []
    for bd in boarding_data:
        days = (getdate(bd.date_out) - getdate(bd.date_in)).days if bd.date_out and bd.date_in else "?"
        boarding_lines.append(
            f"  {bd.name} | {bd.owner_name_and_surname} | {bd.date_in}→{bd.date_out or '?'} ({days} days)"
            f" | R{flt(bd.total_cost):,.0f} (paid R{flt(bd.amount_paid):,.0f}, owing R{flt(bd.outstanding):,.0f})"
        )
    boarding_str = "\n".join(boarding_lines) if boarding_lines else "  No active boarding"

    # ── ADOPTION APPLICATION DETAILS ─────────────────────────
    detailed_apps = frappe.get_all("Adoption Application",
        filters={"status": ["in", ["Pending", "Under Review", "Home Check Scheduled", "Home Check Completed", "Approved"]]},
        fields=["name", "applicant_name", "email", "phone", "status", "animal",
                "animal_name", "species_preference", "housing_type", "own_or_rent",
                "has_yard", "yard_fenced", "number_of_adults", "number_of_children",
                "number_of_current_pets", "previous_pet_experience", "application_date"],
        order_by="application_date asc", limit=20
    )
    detailed_app_lines = []
    for a in detailed_apps:
        profile = f"housing={a.housing_type or '?'}, {a.own_or_rent or '?'}"
        if a.has_yard: profile += ", yard"
        if a.yard_fenced: profile += "(fenced)"
        profile += f", adults={a.number_of_adults or '?'}, kids={a.number_of_children or 0}"
        profile += f", current_pets={a.number_of_current_pets or 0}, exp={a.previous_pet_experience or '?'}"
        detailed_app_lines.append(
            f"  {a.name} | {a.applicant_name} ({a.email}, {a.phone}) → {a.animal_name or a.species_preference or 'any'}"
            f" | {a.status} | {profile}"
        )
    detailed_apps_str = "\n".join(detailed_app_lines) if detailed_app_lines else "  None"

    # ── ACTIVE FOSTERS ───────────────────────────────────────
    active_fosters = frappe.get_all("Foster Application",
        filters={"status": "Active"},
        fields=["name", "applicant_name", "animal", "foster_type", "start_date", "expected_end_date"],
        order_by="start_date desc", limit=10
    )
    foster_lines = []
    for f_app in active_fosters:
        animal_name = frappe.db.get_value("Animal", f_app.animal, "animal_name") if f_app.animal else "?"
        foster_lines.append(
            f"  {f_app.name} | {f_app.applicant_name} fostering {animal_name} ({f_app.foster_type})"
            f" | {f_app.start_date}→{f_app.expected_end_date or 'ongoing'}"
        )
    foster_str = "\n".join(foster_lines) if foster_lines else "  No active fosters"

    # ── ANIMAL TRANSFERS (last 30 days) ──────────────────────
    transfers = frappe.get_all("Animal Transfer",
        filters={"date": [">=", add_days(now, -30)]},
        fields=["name", "animal_name", "transfer_type", "from_location", "to_location",
                "date", "reason"],
        order_by="date desc", limit=10
    )
    transfer_lines = []
    for t in transfers:
        transfer_lines.append(
            f"  {t.date} | {t.animal_name} | {t.transfer_type}: {t.from_location or '?'}→{t.to_location or '?'}"
            + (f" | reason: {t.reason}" if t.reason else "")
        )
    transfer_str = "\n".join(transfer_lines) if transfer_lines else "  None in last 30 days"

    # ── BUILD THE SYSTEM PROMPT ──────────────────────────────
    context = f"""You are **Scout**, the expert AI assistant for the **{shelter_name}** Kennel Management System (FurEver).
You have COMPLETE, REAL-TIME access to ALL shelter data. You are the most knowledgeable entity about this shelter.
You think deeply before answering. You cross-reference data to find patterns, anomalies, and actionable insights.
You remember everything in this conversation and use prior context to give increasingly helpful responses.
Current date & time: {now_dt}. User: {frappe.session.user}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LIVE SHELTER DASHBOARD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Animals in shelter: {total_animals}
By status: {status_str}
By species: {species_str}
Long-stay (30+ days): {long_stay_count}
Kennel occupancy: {k_occ}/{k_cap} ({k_rate}%) — {avail_kennels} available kennels
Full kennels: {full_kennel_names}
Active boarding animals: {active_boarding}

Adoption applications: {pending_adoptions} pending, {approved_adoptions} approved, {completed_adoptions} completed (all time)
Foster: {pending_foster} pending applications, {active_foster} active fosters
Volunteers: {active_volunteers} active
Donations this month: R {donation_total:,.0f} from {donation_count} donations
Lost & Found: {open_lost} open lost reports, {open_found} open found reports
Daily rounds today: {rounds_today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TODAY'S VET APPOINTMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{vet_str}

Upcoming (next 7 days):
{upcoming_vet_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TODAY'S FEEDING ROUNDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{feeding_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECENT ADMISSIONS (last 7 days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{admission_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECENT ADOPTIONS (last 30 days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{adoption_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PENDING ADOPTION APPLICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{pending_app_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADOPTION APPLICANT PROFILES (active applications)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{detailed_apps_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VETERINARY RECORDS (last 30 days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{vet_records_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VACCINATIONS (last 90 days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{vacc_str}

Overdue vaccinations:
{overdue_vacc_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTIVE MEDICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{med_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BEHAVIOR ASSESSMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{behavior_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTIVE BOARDING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{boarding_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTIVE FOSTERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{foster_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOST & FOUND (open cases)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{lf_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECENT TRANSFERS (last 30 days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{transfer_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALL KENNELS (detailed)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{kennel_detail_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETE ANIMAL ROSTER ({len(all_animals)} animals)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{animal_roster}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETE SYSTEM KNOWLEDGE — DOCTYPES & FIELDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The FurEver system has these doctypes (forms). You know EVERY field and can explain any part:

**Animal** (KM-ANM-): animal_name, species (Dog/Cat/Bird/Rabbit/Reptile/Small Animal/Farm Animal/Other), breed, color, gender (Male/Female/Unknown), date_of_birth, estimated_age_years, estimated_age_months, weight_kg, size (Tiny/Small/Medium/Large/Giant), animal_photo, microchip_number, tattoo_number, rabies_tag, intake_date, source (Stray/Owner Surrender/Rescue/Transfer/Born in Shelter/Confiscation/Return), status (Available for Adoption/Adopted/In Foster Care/Medical Hold/Behavior Hold/Quarantine/Stray Hold/In Treatment/Reserved/Transferred/Deceased/Returned to Owner/Lost in Care), temperament (Friendly/Shy/Aggressive/Fearful/Playful/Calm/Anxious/Independent), spay_neuter_status, is_special_needs, current_kennel→Kennel, good_with_dogs/cats/children, house_trained, energy_level, outcome_type, adopted_by, adoption_fee

**Kennel**: kennel_name, kennel_type (Indoor/Outdoor/Indoor-Outdoor/Isolation/Quarantine/Nursery/Recovery), section, building, capacity, current_occupancy, status (Available/Occupied/Full/Cleaning/Maintenance/Reserved/Out of Service), size_category, has_outdoor_access/heating/cooling/camera, is_isolation, is_quarantine

**Animal Admission** (KM-ADM-): admission_date, admission_type (Stray/Owner Surrender/Rescue/Transfer In/Born in Shelter/Confiscation/Return from Adoption/Return from Foster), admitted_by, priority (Low/Medium/High/Emergency), status (Draft/Processing/Completed/Cancelled), animal→Animal, animal_name_field, species, breed, gender, estimated_age, weight_on_arrival, condition_on_arrival (Excellent/Good/Fair/Poor/Critical), initial_temperament, assigned_kennel→Kennel, requires_quarantine

**Adoption Application** (KM-ADP-): applicant_name, email, phone, status (Pending/Under Review/Home Check Scheduled/Home Check Completed/Approved/Rejected/Adoption Completed/Withdrawn/Waitlisted), animal→Animal, species_preference, housing_type, own_or_rent, has_yard, yard_fenced, number_of_adults/children, number_of_current_pets, previous_pet_experience, vet_name, adoption_date, adoption_fee

**Veterinary Appointment** (KM-VET-): animal→Animal, appointment_date, appointment_time, status (Scheduled/Checked In/In Progress/Completed/Cancelled/No Show/Rescheduled), priority (Routine/Urgent/Emergency), appointment_type (Intake Exam/Wellness Check/Vaccination/Spay-Neuter/Surgery/Dental/Emergency/Follow-up/Lab Work/X-Ray/Microchipping/etc.), veterinarian→User, diagnosis, treatment_plan, medications→Medication Item, followup_required, total_cost

**Veterinary Record** (KM-VR-): animal→Animal, date, record_type (Examination/Vaccination/Surgery/Treatment/Lab Results/Dental/Emergency/Behavior/Other), veterinarian→User, description, treatment, vaccinations→Vaccination Item (vaccine_name, date_administered, next_due_date), medications→Medication Item

**Feeding Round** (KM-FR-): date, shift (Morning 7AM/Afternoon 3PM), assigned_to→User, status (Draft/In Progress/Completed/Overdue), animals→Feeding Round Detail, total_animals, animals_fed, completion_percentage

**Daily Round** (KM-DR-): date, round_type (Morning/Midday/Afternoon/Evening/Night/Emergency), inspector→User, status (Draft/In Progress/Completed), animals→Daily Round Detail, animals_needing_attention, issues_found

**Boarding Animal Form** (KM-BRD-): date_in, date_out, cost_per_day, total_cost, amount_paid, outstanding, receipt_no, proof_of_vaccinations, status (Active/Completed/Cancelled/Abandoned), owner_name_and_surname, cell_number, email, animals→Boarding Animal Detail (breed, age, sex, sterilized, colour, vaccinations, animal_name, kennel_number)

**Donation** (KM-DON-): donor_name, donation_date, donation_type (Monetary/Supplies/Services/Sponsorship/Legacy), amount, payment_method, receipt_number, tax_deductible, campaign

**Volunteer** (KM-VOL-): full_name, email, phone, status (Applied/Active/Inactive/Suspended/Resigned), start_date, available_days, available_shift, hours_per_week, skills, background_check_status, total_hours_volunteered

**Foster Application** (KM-FOS-): applicant_name, status (Pending/Approved/Active/Completed/Rejected/Withdrawn), animal→Animal, foster_type (Short/Medium/Long Term/Medical/Neonatal/Behavior/Hospice), start_date, expected_end_date

**Lost and Found Report** (KM-LF-): report_type (Lost/Found/Sighted), status (Open/Investigating/Matched/Reunited/Closed), reporter_name, species, breed, color, last_seen_location, last_seen_date, matched_animal→Animal

**Behavior Assessment** (KM-BA-): animal→Animal, assessment_date, assessor→User, approach_response, handling_tolerance, overall_temperament, dog/cat_sociability, stranger/child_reaction, resource/food/toy_guarding, basic_commands, leash_behavior, energy_level, aggression/fear/sociability/trainability scores (1-5)

**Kennel Management Settings**: shelter_name, AI config (provider/key/model/vision model/temp/tokens), TTS/STT config, SMS/WhatsApp/Email config, adoption settings (fees, stray hold days, home check req), kennel settings (quarantine days, capacity warning), feeding schedule (morning 7AM, afternoon 3PM, overdue alerts), daily round settings

**PDF Print Builder**: Visual tool to create print formats by overlaying fields on PDF backgrounds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFLOWS & PROCESSES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• **Admission flow**: Create Animal Admission → fills species/breed/gender/condition → assigns kennel → creates Animal record → optional quarantine
• **Adoption flow**: Application submitted → Under Review → Home Check Scheduled → Home Check Completed → Approved → Adoption Completed (updates Animal status)
• **Vet flow**: Schedule Appointment → Check In → In Progress → Completed → creates Veterinary Record with vaccinations/medications
• **Feeding**: Auto-generated rounds at 7AM & 3PM → staff marks each animal as fed → completion tracked → overdue alerts after 60min
• **Daily rounds**: Auto-generated morning checks → inspector records observations per animal → flags animals needing attention
• **Boarding**: Owner brings animal → fill Boarding Animal Form → date in/out, cost calculated → indemnity signed → animal collected
• **Foster**: Application submitted → reviewed → approved → animal placed → foster period → animal returned or adopted
• **Lost & Found**: Report filed → investigation → matched with animal/report → reunited → closed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NAVIGATION URLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dashboard: /app/kennel-dashboard
Animals: /app/animal | New: /app/animal/new | Specific: /app/animal/KM-ANM-XXXX-XXXXX
Kennels: /app/kennel | Specific: /app/kennel/[kennel-name]
Admissions: /app/animal-admission | New: /app/animal-admission/new
Vet Appointments: /app/veterinary-appointment | New: /app/veterinary-appointment/new
Vet Records: /app/veterinary-record
Adoption Applications: /app/adoption-application | Pending: /app/adoption-application?status=Pending
Feeding Rounds: /app/feeding-round | Today: /app/feeding-round?date={now}
Feeding Schedules: /app/feeding-schedule
Daily Rounds: /app/daily-round | Today: /app/daily-round?date={now}
Boarding: /app/boarding-animal-form | Active: /app/boarding-animal-form?status=Active
Donations: /app/donation | New: /app/donation/new
Volunteers: /app/volunteer | Active: /app/volunteer?status=Active
Foster: /app/foster-application
Lost & Found: /app/lost-and-found-report | Open: /app/lost-and-found-report?status=Open
Behavior Assessment: /app/behavior-assessment
Settings: /app/kennel-management-settings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR CAPABILITIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You can:
• Answer ANY question about the shelter's animals, kennels, operations, staff, finances
• Find specific animals by name, breed, species, status, kennel, or any attribute
• Report on kennel occupancy, capacity alerts, available spaces
• Track vet appointments, medical histories, vaccination schedules, overdue vaccinations
• Review adoption applications, suggest matches between animals and adopters based on detailed applicant profiles
• Monitor feeding rounds — who's been fed, who hasn't, overdue alerts
• Report on daily health rounds and flag concerns
• Track boarding animals, costs, dates, outstanding payments
• Report on donations, fundraising progress
• Manage volunteer information and availability
• Help with lost & found cases — cross-reference found reports with lost reports and shelter animals
• Explain any workflow or process in the system
• Provide navigation links to any form or list in the system
• Identify dog breeds from photos (via vision)
• Guide staff through intake, adoption, vet, and foster procedures step by step
• Track active medications and flag animals needing attention
• Review behavior assessments and recommend adoption suitability
• Cross-reference applicant profiles with animal temperaments for ideal matching
• Identify animals with overdue vaccinations, assessments, or medical follow-ups
• Spot trends: intake patterns, adoption rates, length-of-stay outliers, cost analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THINKING & REASONING APPROACH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before answering, THINK through the data:
1. What specific data points are relevant to this question?
2. Are there cross-references I should make? (e.g., animal's behavior assessment + adoption applicant's profile)
3. Are there any red flags, urgent issues, or anomalies in the data I should proactively mention?
4. What actionable recommendation can I make?
5. Is there relevant conversation history I should reference?

You have FULL conversation history. Use it to:
• Track what the user already asked about — don't repeat info unnecessarily
• Understand follow-up questions: "what about her vaccinations?" refers to the last animal discussed
• Build on previous answers: "you mentioned Kennel B3 is full — where should we put the new dog?"
• Remember user preferences and context from earlier in the chat

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Use the REAL data above — never make up numbers or animal names
2. Use **bold** for names, numbers, and important values
3. Be thorough and comprehensive — give everything they need. Don't hold back information to keep things short.
4. When referring to animals, use their actual names and IDs from the roster
5. Provide relevant navigation links when helpful
6. If asked about something not in your data, say so honestly and suggest where to look
7. For operational questions, refer to actual current counts and stats
8. Be warm, confident, and knowledgeable — you're the shelter's expert AI
9. When asked "how do I..." questions, provide step-by-step instructions with URLs
10. Use emoji sparingly — one per message max, only when appropriate
11. Be PROACTIVE: spot potential issues in the data and mention them (e.g., animals in shelter 60+ days, full kennels approaching capacity, overdue vet appointments, unfed animals, low adoption rates, overdue vaccinations, animals on medication needing follow-up)
12. Cross-reference data to give INSIGHTS, not just raw numbers (e.g., "Bella has been here 45 days, her behavior assessment shows she's friendly with kids — she'd be perfect for the Jones family application that just came in" or "Kennel B3 is full but A2 has space and is the right type for quarantine")
13. When asked about a specific animal, give a COMPLETE profile: name, species, breed, age, weight, temperament, kennel location, medical history, vaccinations (any overdue?), behavior assessment results, medications, how long they've been here, compatibility info, adoption suitability — everything you know from ALL data sections
14. For adoption recommendations, cross-reference the APPLICANT PROFILES section with animal behavior assessments: match energy levels, living situation (yard/apartment), experience with breed, family composition (kids/pets), temperament compatibility
15. When discussing capacity or trends, provide context and a recommendation: "We're at 87% capacity which is above the 80% comfort zone — consider promoting these long-stay animals: [names]. Also 3 animals have approved adoptions pending pickup."
16. You are an EXPERT in animal shelter management — proactively offer best-practice advice
17. For medical questions, check veterinary records, active medications, vaccinations, and flag any overdue follow-ups
18. When asked about lost & found, cross-reference open lost reports with recently found animals and shelter intake matching species/breed/color
19. Calculate things when asked: costs, days in shelter, vaccination schedules, boarding charges, occupancy percentages
20. If the user asks a vague question, provide the MOST useful interpretation and answer comprehensively

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHELTER MANAGEMENT EXPERTISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You have deep knowledge of animal shelter best practices:
• Quarantine: new arrivals should be isolated 7-14 days; monitor for respiratory illness, parasites, parvo/distemper
• Intake triage: assess condition (critical→emergency vet, poor→medical hold, fair/good→standard processing)
• Behavior assessment: use the SAFER or ASPCA approach — evaluate approach response, handling, dog/cat/child sociability, resource guarding
• Adoption matching: match energy levels, living situation (yard/apartment), experience with breed, family composition
• Length-of-stay management: animals over 30 days need enrichment plans, photo updates, social media promotion
• Disease prevention: keep isolation/quarantine separate from general population, proper cleaning protocols between kennels
• Feeding: twice daily (7AM & 3PM), monitor appetite changes as early illness indicator
• Daily rounds: check every animal twice daily for signs of illness, stress, injury
• Foster programs: reduce shelter stress, free kennel space, socialize animals — prioritize neonates, medical cases, and long-stay animals"""

    # Voice mode: add special instructions for spoken-friendly responses
    if voice_mode:
        context += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ VOICE CONVERSATION MODE — ACTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The user is speaking to you via voice. Your response will be read aloud by text-to-speech.
CRITICAL RULES for voice mode:
• Keep responses SHORT — 1-3 sentences max. Be conversational, like talking to a colleague.
• NO markdown formatting: no **bold**, no bullet points (•), no numbered lists, no links, no URLs.
• Use natural spoken language: "We have 42 animals right now, 28 of them are dogs" not "**42** animals\n• 28 Dogs"
• Pronounce numbers naturally: "twelve" not "12" for small numbers, but large numbers like "forty-two" are fine either way.
• Skip navigation links — just answer the question directly.
• If they ask something complex, give the key answer first, then offer to elaborate: "Bella is a 3 year old Labrador in kennel A5, she's been here about 2 months. Want me to tell you more about her?"
• Sound warm and natural — imagine you're a knowledgeable coworker answering a quick question."""

    return context


def _call_openai(api_key, model, context, message, max_tokens=4096, temperature=0.4, conversation_history=None):
    """Call OpenAI API with multi-turn conversation."""
    import requests

    messages = [{"role": "system", "content": context}]
    for msg in (conversation_history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"OpenAI API error {resp.status_code}: {resp.text[:500]}", "OpenAI API Error")
    return None


def _call_anthropic(api_key, model, context, message, max_tokens=4096, temperature=0.4, conversation_history=None):
    """Call Anthropic API with multi-turn conversation."""
    import requests

    messages = []
    for msg in (conversation_history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

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
            "temperature": temperature,
            "system": context,
            "messages": messages
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["content"][0]["text"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"Anthropic API error {resp.status_code}: {resp.text[:500]}", "Anthropic API Error")
    return None


def _call_gemini(api_key, model, context, message, max_tokens=4096, temperature=0.4, conversation_history=None):
    """Call Google Gemini API with multi-turn conversation."""
    import requests

    contents = []
    for msg in (conversation_history or []):
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": context}]},
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"Gemini API error {resp.status_code}: {resp.text[:500]}", "Gemini API Error")
    return None


def _call_groq(api_key, model, context, message, max_tokens=4096, temperature=0.4, conversation_history=None):
    """Call Groq API (OpenAI-compatible) with multi-turn conversation."""
    import requests

    messages = [{"role": "system", "content": context}]
    for msg in (conversation_history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"Groq API error {resp.status_code}: {resp.text[:500]}", "Groq API Error")
    return None


def _call_mistral(api_key, model, context, message, max_tokens=4096, temperature=0.4, conversation_history=None):
    """Call Mistral API with multi-turn conversation."""
    import requests

    messages = [{"role": "system", "content": context}]
    for msg in (conversation_history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    resp = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"Mistral API error {resp.status_code}: {resp.text[:500]}", "Mistral API Error")
    return None


def _call_deepseek(api_key, model, context, message, max_tokens=4096, temperature=0.4, conversation_history=None):
    """Call DeepSeek API (OpenAI-compatible) with multi-turn conversation."""
    import requests

    messages = [{"role": "system", "content": context}]
    for msg in (conversation_history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"DeepSeek API error {resp.status_code}: {resp.text[:500]}", "DeepSeek API Error")
    return None


def _call_ollama(model, context, message, max_tokens=4096, temperature=0.4, conversation_history=None):
    """Call Ollama local API with multi-turn conversation."""
    import requests

    messages = [{"role": "system", "content": context}]
    for msg in (conversation_history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": messages,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature
                },
                "stream": False
            },
            timeout=120
        )

        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("message", {}).get("content", "")
            if reply:
                return {"reply": reply, "actions": []}
    except requests.exceptions.ConnectionError:
        frappe.log_error("Ollama is not running. Start it with 'ollama serve'", "Ollama Connection Error")

    return None


# ─── Text-to-Speech ──────────────────────────────────────────────────
@frappe.whitelist()
def text_to_speech(text=None):
    """Convert text to speech audio using OpenAI TTS API. Returns base64 MP3."""
    import requests
    import base64

    if not text:
        return {"error": "No text provided"}

    settings = frappe.get_single("Kennel Management Settings")
    tts_provider = getattr(settings, "tts_provider", "Browser Default")

    if tts_provider != "OpenAI TTS":
        return {"provider": "browser"}  # Signal JS to use browser TTS

    tts_api_key = settings.get_password("tts_api_key") if settings.tts_api_key else None
    if not tts_api_key:
        # Fall back to main AI API key if OpenAI is the AI provider
        ai_provider = getattr(settings, "ai_provider", "")
        if ai_provider == "OpenAI":
            tts_api_key = settings.get_password("ai_api_key") if settings.ai_api_key else None

    if not tts_api_key:
        return {"provider": "browser"}

    voice = getattr(settings, "tts_voice", "") or "nova"
    # Clean text for speech
    import re
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    cleaned = re.sub(r'[•\n]+', '. ', cleaned)
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)  # Remove markdown links
    cleaned = re.sub(r'[#>`]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if not cleaned or len(cleaned) < 2:
        return {"error": "Text too short"}

    # Truncate to 4096 chars (OpenAI TTS limit)
    if len(cleaned) > 4096:
        cleaned = cleaned[:4093] + "..."

    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {tts_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "tts-1",
                "input": cleaned,
                "voice": voice,
                "response_format": "mp3"
            },
            timeout=30
        )

        if resp.status_code == 200:
            audio_b64 = base64.b64encode(resp.content).decode("utf-8")
            return {
                "audio": audio_b64,
                "format": "mp3",
                "provider": "openai"
            }
        else:
            frappe.log_error(f"OpenAI TTS error {resp.status_code}: {resp.text[:500]}", "TTS Error")
            return {"provider": "browser"}  # Fall back

    except Exception:
        frappe.log_error(frappe.get_traceback(), "TTS Error")
        return {"provider": "browser"}


# ─── Speech-to-Text ──────────────────────────────────────────────────
@frappe.whitelist()
def speech_to_text(audio_data=None):
    """Transcribe audio using OpenAI Whisper API. Accepts base64 webm/wav."""
    import requests
    import base64

    if not audio_data:
        return {"error": "No audio provided"}

    settings = frappe.get_single("Kennel Management Settings")
    stt_provider = getattr(settings, "stt_provider", "Browser Default")

    if stt_provider != "OpenAI Whisper":
        return {"provider": "browser"}

    stt_api_key = settings.get_password("stt_api_key") if settings.stt_api_key else None
    if not stt_api_key:
        ai_provider = getattr(settings, "ai_provider", "")
        if ai_provider == "OpenAI":
            stt_api_key = settings.get_password("ai_api_key") if settings.ai_api_key else None

    if not stt_api_key:
        return {"provider": "browser"}

    language = getattr(settings, "stt_language", "en-US") or "en"
    lang_code = language.split("-")[0]  # "en-US" → "en"

    try:
        # Strip data URL prefix
        raw_b64 = audio_data
        if "," in audio_data:
            raw_b64 = audio_data.split(",", 1)[1]

        audio_bytes = base64.b64decode(raw_b64)

        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {stt_api_key}"},
            files={"file": ("audio.webm", audio_bytes, "audio/webm")},
            data={"model": "whisper-1", "language": lang_code},
            timeout=30
        )

        if resp.status_code == 200:
            data = resp.json()
            return {"text": data.get("text", ""), "provider": "openai"}
        else:
            frappe.log_error(f"Whisper STT error {resp.status_code}: {resp.text[:500]}", "STT Error")
            return {"provider": "browser"}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "STT Error")
        return {"provider": "browser"}


# ─── Vision AI ───────────────────────────────────────────────────────
@frappe.whitelist()
def chatbot_vision_query(image_data=None, message=None):
    """Analyze an image using Vision AI — breed identification, health, age estimation."""
    import json as json_mod

    if not image_data:
        return {"reply": "No image provided. Please upload or take a photo.", "actions": []}

    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_ai_chatbot", False):
        return {"reply": "AI is not enabled. Go to **Settings → AI & Intelligence** to configure a provider.", "actions": []}

    ai_provider = getattr(settings, "ai_provider", None)
    api_key = settings.get_password("ai_api_key") if settings.ai_api_key else None
    vision_model = getattr(settings, "ai_vision_model", None)
    max_tokens = getattr(settings, "ai_max_tokens", 1000) or 1000

    # Vision-capable providers
    vision_providers = {
        "OpenAI": {"model": vision_model or "gpt-4o", "endpoint": "openai"},
        "Anthropic": {"model": vision_model or "claude-sonnet-4-20250514", "endpoint": "anthropic"},
        "Google Gemini": {"model": vision_model or "gemini-2.0-flash", "endpoint": "gemini"},
        "Ollama (Local)": {"model": vision_model or "llava", "endpoint": "ollama"},
    }

    if ai_provider not in vision_providers:
        return {
            "reply": f"Vision analysis requires **OpenAI**, **Anthropic**, **Google Gemini**, or **Ollama** (with llava). "
                     f"Current provider: {ai_provider or 'None'}. Change it in Settings → AI & Intelligence.",
            "actions": [{"label": "Open Settings", "route": "/app/kennel-management-settings"}]
        }

    if ai_provider != "Ollama (Local)" and not api_key:
        return {"reply": "API key not configured. Set it in **Settings → AI & Intelligence**.", "actions": []}

    # Build the vision prompt
    prompt = message or "Analyze this image."
    system_prompt = (
        "You are Scout Vision AI, an expert veterinary and animal identification assistant for an SPCA shelter. "
        "When shown a photo of an animal, provide:\n"
        "1. **Breed Identification** — primary breed, possible mix. Be specific.\n"
        "2. **Estimated Age** — puppy/juvenile/adult/senior with approximate range\n"
        "3. **Size Category** — small/medium/large/extra-large with estimated weight\n"
        "4. **Visible Health Observations** — coat condition, body condition score (1-9), any visible issues\n"
        "5. **Temperament Guess** — based on body language and expression in the photo\n"
        "6. **Suggested Name** — a fun shelter name if none is given\n"
        "7. **Care Notes** — breed-specific needs, exercise level, grooming needs\n\n"
        "If the image is NOT an animal, say so clearly. Be confident and specific in your assessments. "
        "Use **bold** formatting for headings and key info."
    )

    try:
        provider_info = vision_providers[ai_provider]

        # Strip data URL prefix to get raw base64
        base64_data = image_data
        media_type = "image/jpeg"
        if "," in image_data:
            header, base64_data = image_data.split(",", 1)
            if "png" in header:
                media_type = "image/png"
            elif "webp" in header:
                media_type = "image/webp"

        if provider_info["endpoint"] == "openai":
            result = _call_openai_vision(api_key, provider_info["model"], system_prompt, prompt, image_data, max_tokens)
        elif provider_info["endpoint"] == "anthropic":
            result = _call_anthropic_vision(api_key, provider_info["model"], system_prompt, prompt, base64_data, media_type, max_tokens)
        elif provider_info["endpoint"] == "gemini":
            result = _call_gemini_vision(api_key, provider_info["model"], system_prompt, prompt, base64_data, media_type, max_tokens)
        elif provider_info["endpoint"] == "ollama":
            result = _call_ollama_vision(provider_info["model"], system_prompt, prompt, base64_data, max_tokens)
        else:
            result = None

        if result:
            return result

        return {"reply": "Vision analysis failed. The AI provider may not have returned a valid response.", "actions": []}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Vision AI Error")
        return {"reply": "An error occurred during image analysis. Check the error log for details.", "actions": []}


def _call_openai_vision(api_key, model, system, prompt, image_data_url, max_tokens=1000):
    """Call OpenAI Vision API with image."""
    import requests

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url, "detail": "high"}}
                ]}
            ],
            "max_tokens": max_tokens,
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"OpenAI Vision API error {resp.status_code}: {resp.text[:500]}", "OpenAI Vision Error")
    return None


def _call_anthropic_vision(api_key, model, system, prompt, base64_data, media_type, max_tokens=1000):
    """Call Anthropic Vision API with image."""
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
            "system": system,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["content"][0]["text"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"Anthropic Vision API error {resp.status_code}: {resp.text[:500]}", "Anthropic Vision Error")
    return None


def _call_gemini_vision(api_key, model, system, prompt, base64_data, media_type, max_tokens=1000):
    """Call Google Gemini Vision API with image."""
    import requests

    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": media_type, "data": base64_data}}
                ]
            }],
            "generationConfig": {"maxOutputTokens": max_tokens}
        },
        timeout=60
    )

    if resp.status_code == 200:
        data = resp.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        return {"reply": reply, "actions": []}

    frappe.log_error(f"Gemini Vision API error {resp.status_code}: {resp.text[:500]}", "Gemini Vision Error")
    return None


def _call_ollama_vision(model, system, prompt, base64_data, max_tokens=1000):
    """Call Ollama local vision model (llava, bakllava, etc.)."""
    import requests

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt, "images": [base64_data]}
                ],
                "options": {"num_predict": max_tokens},
                "stream": False
            },
            timeout=120
        )

        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("message", {}).get("content", "")
            if reply:
                return {"reply": reply, "actions": []}
    except requests.exceptions.ConnectionError:
        return {"reply": "Ollama is not running. Start it with `ollama serve` and ensure a vision model (e.g., `llava`) is pulled.", "actions": []}
    return None


# ─── Document Scanning / OCR ─────────────────────────────────────────
@frappe.whitelist()
def chatbot_document_scan(image_data=None, hint=None):
    """Read and extract structured data from handwritten / printed documents."""
    import json as json_mod

    if not image_data:
        return {"reply": "No document image provided. Please upload or photograph the document.", "actions": []}

    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_ai_chatbot", False):
        return {"reply": "AI is not enabled. Configure it in **Settings → AI & Intelligence**.", "actions": []}

    ai_provider = getattr(settings, "ai_provider", None)
    api_key = settings.get_password("ai_api_key") if settings.ai_api_key else None
    vision_model = getattr(settings, "ai_vision_model", None)
    max_tokens = min(getattr(settings, "ai_max_tokens", 2000) or 2000, 4000)

    # Vision-capable providers only
    vision_providers = {
        "OpenAI": {"model": vision_model or "gpt-4o", "endpoint": "openai"},
        "Anthropic": {"model": vision_model or "claude-sonnet-4-20250514", "endpoint": "anthropic"},
        "Google Gemini": {"model": vision_model or "gemini-2.0-flash", "endpoint": "gemini"},
        "Ollama (Local)": {"model": vision_model or "llava", "endpoint": "ollama"},
    }

    if ai_provider not in vision_providers:
        return {
            "reply": "Document scanning requires a vision-capable AI provider (**OpenAI**, **Anthropic**, **Google Gemini**, or **Ollama**).",
            "actions": [{"label": "Open Settings", "route": "/app/kennel-management-settings"}]
        }

    if ai_provider != "Ollama (Local)" and not api_key:
        return {"reply": "API key not configured. Set it in **Settings → AI & Intelligence**.", "actions": []}

    # Build OCR / document reading prompt
    hint_text = f"\n\nAdditional context from the user: {hint}" if hint else ""
    system_prompt = (
        "You are Scout Document Reader — an expert OCR and handwriting recognition AI for an SPCA / animal shelter.\n\n"
        "YOUR CAPABILITIES:\n"
        "- Read ALL handwriting styles: cursive, print, block letters, messy/doctor's handwriting, child handwriting, "
        "mixed case, abbreviations, crossed-out text, marginal notes\n"
        "- Read printed text, typed forms, stamps, checkboxes (checked ☑ / unchecked ☐)\n"
        "- Handle poor quality: faded ink, smudged, creased, partially torn, coffee-stained, low resolution\n"
        "- Read multiple languages (default English, detect Afrikaans/Zulu if present)\n"
        "- Understand form layouts: tables, columns, labelled fields, free-text areas\n\n"
        "DOCUMENT TYPES YOU HANDLE:\n"
        "- Animal intake / admission forms\n"
        "- Owner surrender forms\n"
        "- Adoption application forms\n"
        "- Veterinary examination records\n"
        "- Vaccination cards / certificates\n"
        "- Microchip registration documents\n"
        "- Client ID documents (SA ID, passport, driver's license)\n"
        "- Donation receipts\n"
        "- Lost & found reports\n"
        "- Handwritten notes from staff\n"
        "- Any other shelter-related paperwork\n\n"
        "OUTPUT FORMAT:\n"
        "1. First, provide a **human-readable summary** of everything on the document, using bold headings and bullet points.\n"
        "2. Then output a JSON code block (```json ... ```) with ALL extracted fields as key-value pairs. Use snake_case keys.\n"
        "   Standard keys to include when found:\n"
        "   - animal_name, breed, species, age, approximate_age, gender, color, markings\n"
        "   - microchip, microchipped, sterilized, vaccination\n"
        "   - intake_type, reason, date, health_notes, medical, conditions\n"
        "   - weight, temperature, diagnosis, treatment, medication, vet_notes\n"
        "   - client_name, owner_name, full_name, phone, email, address, id_number\n"
        "   - purpose, notes, signature_present\n"
        "   - _raw_text (full OCR text of the entire document)\n"
        "   - _document_type (what type of document this is)\n"
        "   - _confidence (your confidence level: high/medium/low)\n\n"
        "HANDWRITING RULES:\n"
        "- If a word is ambiguous, provide your best guess and note '[uncertain]' after it\n"
        "- For illegible sections, write '[illegible]' and describe what you can see\n"
        "- Expand common abbreviations: 'M' → 'Male', 'F' → 'Female', 'GSD' → 'German Shepherd Dog', "
        "'vacc' → 'vaccinated', 'steril' → 'sterilized', 'yr' → 'year', 'mo' → 'month'\n"
        "- Read dates in any format and normalize to YYYY-MM-DD\n"
        "- Read checkboxes: ✓/X/filled = checked, empty = unchecked\n"
        "- If the form has numbered fields, keep the numbering in your output\n\n"
        "Be thorough — extract EVERY piece of information visible on the document."
        + hint_text
    )

    prompt = "Read this document completely. Extract all handwritten and printed text. Identify every field and its value."
    if hint:
        prompt += f" The user says: {hint}"

    try:
        provider_info = vision_providers[ai_provider]

        # Strip data URL prefix
        base64_data = image_data
        media_type = "image/jpeg"
        if "," in image_data:
            header, base64_data = image_data.split(",", 1)
            if "png" in header:
                media_type = "image/png"
            elif "webp" in header:
                media_type = "image/webp"

        if provider_info["endpoint"] == "openai":
            result = _call_openai_vision(api_key, provider_info["model"], system_prompt, prompt, image_data, max_tokens)
        elif provider_info["endpoint"] == "anthropic":
            result = _call_anthropic_vision(api_key, provider_info["model"], system_prompt, prompt, base64_data, media_type, max_tokens)
        elif provider_info["endpoint"] == "gemini":
            result = _call_gemini_vision(api_key, provider_info["model"], system_prompt, prompt, base64_data, media_type, max_tokens)
        elif provider_info["endpoint"] == "ollama":
            result = _call_ollama_vision(provider_info["model"], system_prompt, prompt, base64_data, max_tokens)
        else:
            result = None

        if result and result.get("reply"):
            # Try to extract JSON from the response
            extracted = _extract_json_from_reply(result["reply"])
            result["extracted_data"] = extracted
            return result

        return {"reply": "Could not read the document. Try a clearer photo with better lighting.", "actions": []}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Document Scan Error")
        return {"reply": "An error occurred during document scanning. Check the error log.", "actions": []}


def _extract_json_from_reply(text):
    """Extract JSON object from AI reply that may contain markdown code blocks."""
    import json as json_mod
    import re

    # Try to find ```json ... ``` block
    match = re.search(r'```json\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if match:
        try:
            return json_mod.loads(match.group(1))
        except (json_mod.JSONDecodeError, ValueError):
            pass

    # Try to find any { ... } block
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            return json_mod.loads(match.group(0))
        except (json_mod.JSONDecodeError, ValueError):
            pass

    return None


# ─── AI-Powered Admission & Client Info ──────────────────────────────
@frappe.whitelist()
def ai_create_admission(admission_data=None):
    """Create an Animal + Animal Admission from chatbot-collected data (full fields)."""
    import json as json_mod
    from frappe.utils import today, nowdate, now_datetime

    if not admission_data:
        return {"success": False, "error": "No admission data provided"}

    try:
        data = json_mod.loads(admission_data) if isinstance(admission_data, str) else admission_data

        # Determine initial status based on quarantine
        wants_quarantine = data.get("requires_quarantine", 0)
        initial_status = "Quarantine" if wants_quarantine else "Available for Adoption"

        # Map spay/neuter to Animal field
        spay_map = {"Yes": "Spayed", "No": "Intact", "Unknown": "Intact"}
        spay_status = spay_map.get(data.get("is_spayed_neutered", "Unknown"), "Intact")

        # Create the animal record
        animal = frappe.new_doc("Animal")
        animal.animal_name = data.get("animal_name", "Unknown Intake")
        animal.species = data.get("species", "Dog")
        animal.breed = data.get("breed", "")
        animal.gender = data.get("gender", "Unknown")
        animal.color = data.get("color", "")
        animal.status = initial_status
        animal.intake_date = today()
        animal.source = data.get("admission_type", "Stray")
        animal.spay_neuter_status = spay_status
        animal.temperament = data.get("initial_temperament", "")

        # Parse estimated age into years/months
        age_raw = (data.get("estimated_age") or "").lower().strip()
        if age_raw and age_raw != "unknown":
            import re
            yr_match = re.search(r"(\d+)\s*(?:year|yr|y)", age_raw)
            mo_match = re.search(r"(\d+)\s*(?:month|mo|m)", age_raw)
            age_word_map = {"puppy": (0, 6), "kitten": (0, 4), "junior": (1, 0),
                            "adult": (3, 0), "senior": (8, 0), "baby": (0, 2)}
            if yr_match:
                animal.estimated_age_years = int(yr_match.group(1))
            if mo_match:
                animal.estimated_age_months = int(mo_match.group(1))
            if not yr_match and not mo_match:
                for word, (y, m) in age_word_map.items():
                    if word in age_raw:
                        animal.estimated_age_years = y
                        animal.estimated_age_months = m
                        break

        # Weight
        weight = data.get("weight_on_arrival")
        if weight:
            try:
                animal.weight_kg = float(weight)
            except (ValueError, TypeError):
                pass

        # Medical flags
        if data.get("is_special_needs"):
            animal.is_special_needs = 1
        if data.get("injuries_description"):
            animal.medical_notes = data["injuries_description"]

        animal.insert(ignore_permissions=True)

        # Create the admission record with all fields
        admission = frappe.new_doc("Animal Admission")
        admission.animal = animal.name
        admission.animal_name_field = animal.animal_name
        admission.species = data.get("species", "Dog")
        admission.breed = data.get("breed", "")
        admission.gender = data.get("gender", "Unknown")
        admission.estimated_age = data.get("estimated_age", "")
        admission.color = data.get("color", "")
        admission.admission_date = now_datetime()
        admission.admission_type = data.get("admission_type", "Stray")
        admission.condition_on_arrival = data.get("condition_on_arrival", "Fair")
        admission.initial_temperament = data.get("initial_temperament", "")
        admission.status = "Processing"
        admission.admitted_by = frappe.session.user
        admission.priority = "Medium"

        # Weight
        if weight:
            try:
                admission.weight_on_arrival = float(weight)
            except (ValueError, TypeError):
                pass

        # Medical/health fields
        admission.is_vaccinated = data.get("is_vaccinated", "Unknown")
        admission.is_spayed_neutered = data.get("is_spayed_neutered", "Unknown")
        admission.is_microchipped = data.get("is_microchipped", "Unknown")
        admission.injuries_description = data.get("injuries_description", "")
        admission.requires_quarantine = 1 if wants_quarantine else 0

        # Source/surrenderer info
        if data.get("surrendered_by_name"):
            admission.surrendered_by_name = data["surrendered_by_name"]
        if data.get("surrendered_by_phone"):
            admission.surrendered_by_phone = data["surrendered_by_phone"]
        if data.get("surrender_reason"):
            admission.surrender_reason = data["surrender_reason"]
        if data.get("found_location"):
            admission.found_location = data["found_location"]

        # Notes
        if data.get("intake_notes"):
            admission.intake_notes = data["intake_notes"]

        admission.insert(ignore_permissions=True)

        # Try to find an available kennel (prefer quarantine if required)
        kennel_name = ""
        try:
            if wants_quarantine:
                available = frappe.db.get_value(
                    "Kennel",
                    {"status": ["in", ["Available", "Empty"]], "is_quarantine": 1},
                    ["name", "kennel_name"], as_dict=True
                )
            else:
                available = None

            if not available:
                available = frappe.db.get_value(
                    "Kennel",
                    {"status": ["in", ["Available", "Empty"]]},
                    ["name", "kennel_name"], as_dict=True
                )

            if available:
                animal.current_kennel = available["name"]
                animal.save(ignore_permissions=True)
                kennel_name = available.get("kennel_name") or available["name"]
                admission.assigned_kennel = available["name"]
                admission.save(ignore_permissions=True)
        except Exception:
            pass  # Kennel assignment is optional

        frappe.db.commit()

        return {
            "success": True,
            "animal": animal.name,
            "animal_name": animal.animal_name,
            "admission": admission.name,
            "kennel": kennel_name,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "AI Admission Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def ai_save_client_info(client_data=None):
    """Save client info collected via chatbot as a ToDo for staff follow-up."""
    import json as json_mod
    from frappe.utils import today

    if not client_data:
        return {"success": False, "error": "No client data provided"}

    try:
        data = json_mod.loads(client_data) if isinstance(client_data, str) else client_data

        purpose_labels = {
            "surrender": "Animal Surrender",
            "adopt": "Adoption Inquiry",
            "report": "Lost/Found Report"
        }
        purpose = purpose_labels.get(data.get("purpose", "").lower(), data.get("purpose", "General Inquiry"))

        description = (
            f"📋 **{purpose}** — Client info collected via AI Assistant\n\n"
            f"**Name:** {data.get('full_name', 'Unknown')}\n"
            f"**Phone:** {data.get('phone', 'Not provided')}\n"
            f"**Email:** {data.get('email', 'Not provided')}\n"
            f"**Address:** {data.get('address', 'Not provided')}\n"
            f"**ID Number:** {data.get('id_number', 'Not provided')}\n"
            f"**Collected by:** {frappe.session.user}\n"
            f"**Date:** {today()}"
        )

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": description,
            "priority": "Medium",
            "date": today(),
            "allocated_to": frappe.session.user,
        })
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "full_name": data.get("full_name", "Unknown"),
            "todo": todo.name,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "AI Client Info Error")
        return {"success": False, "error": str(e)}


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
        SELECT vi.vaccine_name, vi.date_administered, vi.next_due_date
        FROM `tabVaccination Item` vi
        INNER JOIN `tabVeterinary Record` vr ON vi.parent = vr.name
        WHERE vr.animal = %s AND vr.docstatus = 1
        ORDER BY vi.date_administered DESC
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


# ─── PDF Print Builder Helpers ──────────────────────────────────────
@frappe.whitelist()
def get_pdf_page_images(builder_name):
    """Convert PDF pages to base64 images for the print format.

    When printing, we need actual images instead of PDF.js canvas rendering.
    This uses the uploaded PDF file and returns page URLs for use in the print format.
    """
    doc = frappe.get_doc("PDF Print Builder", builder_name)
    if not doc.pdf_file:
        frappe.throw(_("No PDF file attached to this builder."))
    return {"pdf_url": doc.pdf_file, "total_pages": doc.total_pages or 1}


@frappe.whitelist(allow_guest=False)
def get_pdf_page_image(builder=None, page=None):
    """Serve a single PDF page as a PNG image for print format backgrounds.

    Uses PyMuPDF (fitz) if available, otherwise falls back to sending the
    full PDF URL — wkhtmltopdf handles single-page PDFs as images.
    """
    import io

    if not builder or not page:
        frappe.throw(_("builder and page parameters are required."))

    doc = frappe.get_doc("PDF Print Builder", builder)
    if not doc.pdf_file:
        frappe.throw(_("No PDF file attached."))

    page_num = int(page)

    # Try to use PyMuPDF for proper page rendering
    try:
        import fitz  # PyMuPDF

        file_doc = frappe.get_doc("File", {"file_url": doc.pdf_file})
        file_path = file_doc.get_full_path()

        pdf = fitz.open(file_path)
        if page_num < 1 or page_num > len(pdf):
            frappe.throw(_("Page number out of range."))

        pdf_page = pdf[page_num - 1]
        # Render at 200 DPI for good print quality
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = pdf_page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        pdf.close()

        frappe.local.response.filename = f"page_{page_num}.png"
        frappe.local.response.filecontent = img_data
        frappe.local.response.type = "binary"
        frappe.local.response["content_type"] = "image/png"

    except ImportError:
        # PyMuPDF not available — redirect to the PDF file itself
        # wkhtmltopdf can handle this for single-page PDFs
        frappe.local.response.type = "redirect"
        frappe.local.response.location = doc.pdf_file
