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

        # Build shelter context for AI
        from frappe.utils import today, cint, flt
        now = today()
        total_animals = frappe.db.count("Animal", {"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]})
        available = frappe.db.count("Animal", {"status": "Available for Adoption"})
        pending = frappe.db.count("Adoption Application", {"status": ["in", ["Pending", "Under Review"]]})
        appts = frappe.db.count("Veterinary Appointment", {"appointment_date": now, "status": ["!=", "Cancelled"]})

        context = (
            f"You are FurEver Assistant, an AI helper for an SPCA animal shelter management system. "
            f"Current shelter stats: {total_animals} animals in shelter, {available} available for adoption, "
            f"{pending} pending adoption applications, {appts} vet appointments today. "
            f"Today's date: {now}. Be helpful, concise, and friendly. "
            f"Use **bold** for important numbers. If asked about specific records, suggest checking the relevant list."
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
