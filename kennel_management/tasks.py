import frappe
from frappe import _
from frappe.utils import today, add_days, getdate


def send_daily_kennel_summary():
    """Send daily kennel summary to managers."""
    from kennel_management.api import get_dashboard_stats

    stats = get_dashboard_stats()

    settings = frappe.get_single("Kennel Management Settings")
    if not settings.enable_email_notifications or not settings.notification_email:
        return

    message = _(
        """
        <h2>Daily Kennel Summary - {date}</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Animals in Care</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_animals}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Available for Adoption</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{available_for_adoption}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Medical Hold</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{in_medical_hold}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>In Quarantine</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{in_quarantine}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>In Foster Care</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{in_foster}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Pending Adoption Applications</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{pending_adoptions}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Scheduled Vet Appointments</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{scheduled_appointments}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Kennel Availability</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{available_kennels} / {total_kennels}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Adoptions This Month</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{adoptions_this_month}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Admissions This Month</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{admissions_this_month}</td></tr>
        </table>
        """
    ).format(date=today(), **stats)

    frappe.sendmail(
        recipients=[settings.notification_email],
        subject=_("Daily Kennel Summary - {0}").format(today()),
        message=message,
    )


def check_vaccination_reminders():
    """Check for animals with overdue or upcoming vaccinations."""
    upcoming_vaccinations = frappe.db.sql(
        """
        SELECT vi.vaccine_name, vi.next_due_date, vr.animal, vr.animal_name
        FROM `tabVaccination Item` vi
        INNER JOIN `tabVeterinary Record` vr ON vi.parent = vr.name
        WHERE vi.next_due_date BETWEEN %s AND %s
        AND vr.docstatus = 1
        """,
        (today(), add_days(today(), 7)),
        as_dict=True,
    )

    for vax in upcoming_vaccinations:
        # Create a TODO for the kennel manager
        frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": _(
                    "Vaccination reminder: {0} for {1} ({2}) is due on {3}"
                ).format(
                    vax.vaccine_name, vax.animal_name, vax.animal, vax.next_due_date
                ),
                "reference_type": "Animal",
                "reference_name": vax.animal,
                "priority": "High",
            }
        ).insert(ignore_permissions=True)


def check_followup_reminders():
    """Check for vet appointments requiring follow-up."""
    followups = frappe.get_all(
        "Veterinary Appointment",
        filters={
            "followup_required": 1,
            "followup_date": today(),
            "status": "Completed",
        },
        fields=["name", "animal", "animal_name", "veterinarian", "followup_notes"],
    )

    for f in followups:
        frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": _(
                    "Vet follow-up due today for {0} ({1}). Notes: {2}"
                ).format(f.animal_name, f.animal, f.followup_notes or "N/A"),
                "reference_type": "Veterinary Appointment",
                "reference_name": f.name,
                "allocated_to": f.veterinarian,
                "priority": "High",
            }
        ).insert(ignore_permissions=True)


def send_appointment_reminders():
    """Send reminders for upcoming vet appointments."""
    from frappe.utils import now_datetime, add_to_date

    upcoming = frappe.get_all(
        "Veterinary Appointment",
        filters={
            "appointment_date": today(),
            "status": "Scheduled",
        },
        fields=["name", "animal", "animal_name", "veterinarian", "appointment_time", "appointment_type"],
    )

    for apt in upcoming:
        if apt.veterinarian:
            frappe.publish_realtime(
                "appointment_reminder",
                {
                    "appointment": apt.name,
                    "animal": apt.animal_name,
                    "type": apt.appointment_type,
                    "time": str(apt.appointment_time),
                },
                user=apt.veterinarian,
            )


def send_weekly_adoption_report():
    """Send weekly adoption statistics report."""
    settings = frappe.get_single("Kennel Management Settings")
    if not settings.enable_email_notifications or not settings.notification_email:
        return

    week_ago = add_days(today(), -7)

    adoptions = frappe.db.count(
        "Animal",
        filters={
            "outcome_type": "Adoption",
            "outcome_date": [">=", week_ago],
        },
    )

    admissions = frappe.db.count(
        "Animal Admission",
        filters={
            "docstatus": 1,
            "admission_date": [">=", week_ago],
        },
    )

    message = _(
        """
        <h2>Weekly Report</h2>
        <p><strong>Adoptions this week:</strong> {0}</p>
        <p><strong>Admissions this week:</strong> {1}</p>
        """
    ).format(adoptions, admissions)

    frappe.sendmail(
        recipients=[settings.notification_email],
        subject=_("Weekly SPCA Report - {0}").format(today()),
        message=message,
    )


def send_morning_feeding_reminder():
    """Send morning feeding reminder notification."""
    frappe.publish_realtime("feeding_reminder", {"shift": "Morning"})


def send_evening_feeding_reminder():
    """Send evening feeding reminder notification."""
    frappe.publish_realtime("feeding_reminder", {"shift": "Evening"})


def flag_long_stay_animals():
    """Flag animals that have been in the shelter too long and create ToDos."""
    threshold = 30  # days
    cutoff = add_days(today(), -threshold)

    long_stay = frappe.get_all(
        "Animal",
        filters={
            "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
            "intake_date": ["<=", cutoff],
        },
        fields=["name", "animal_name", "intake_date", "species", "status"],
    )

    for animal in long_stay:
        days = (getdate(today()) - getdate(animal.intake_date)).days
        # Only create one todo per animal per week
        existing = frappe.db.exists("ToDo", {
            "reference_type": "Animal",
            "reference_name": animal.name,
            "description": ["like", "%long stay%"],
            "status": "Open",
        })
        if existing:
            continue

        priority = "Urgent" if days > 60 else "High"
        frappe.get_doc({
            "doctype": "ToDo",
            "description": _(
                "🐾 Long stay alert: {0} ({1}) has been in the shelter for {2} days. "
                "Consider promoting for adoption, fostering, or social media features."
            ).format(animal.animal_name, animal.name, days),
            "reference_type": "Animal",
            "reference_name": animal.name,
            "priority": priority,
        }).insert(ignore_permissions=True)


def check_kennel_capacity_alerts():
    """Alert when shelter is approaching capacity."""
    kennels = frappe.get_all(
        "Kennel",
        filters={"status": ["not in", ["Maintenance", "Out of Service"]]},
        fields=["name", "kennel_name", "capacity", "current_occupancy"],
    )

    total_capacity = sum(k.capacity or 0 for k in kennels)
    total_occupancy = sum(k.current_occupancy or 0 for k in kennels)

    if total_capacity == 0:
        return

    utilization = total_occupancy / total_capacity
    if utilization >= 0.9:
        # High capacity alert
        frappe.publish_realtime("kennel_capacity_warning", {
            "utilization": round(utilization * 100, 1),
            "occupancy": total_occupancy,
            "capacity": total_capacity,
            "level": "critical" if utilization >= 0.95 else "warning",
        })

        # Full kennels
        full_kennels = [k for k in kennels if k.current_occupancy >= k.capacity]
        if full_kennels:
            existing = frappe.db.exists("ToDo", {
                "description": ["like", "%Kennel capacity alert%"],
                "status": "Open",
                "date": getdate(today()),
            })
            if not existing:
                names = ", ".join(k.kennel_name for k in full_kennels[:5])
                frappe.get_doc({
                    "doctype": "ToDo",
                    "description": _(
                        "⚠️ Kennel capacity alert: Shelter at {0}% capacity ({1}/{2}). "
                        "Full kennels: {3}"
                    ).format(round(utilization * 100, 1), total_occupancy, total_capacity, names),
                    "priority": "Urgent",
                    "date": getdate(today()),
                }).insert(ignore_permissions=True)


def auto_generate_daily_rounds():
    """Auto-generate daily round entries for all occupied kennels at 7 AM."""
    from kennel_management.api import generate_daily_rounds
    result = generate_daily_rounds()
    if result.get("created"):
        frappe.publish_realtime("daily_rounds_created", {
            "created": result["created"],
            "total_kennels": result["total_kennels"],
        })
