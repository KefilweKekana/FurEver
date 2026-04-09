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
