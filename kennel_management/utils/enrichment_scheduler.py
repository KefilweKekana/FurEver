"""
Animal Enrichment Scheduler — Feature #4
Auto-schedule enrichment activities based on species, temperament, and stay duration.
"""
import frappe
from frappe.utils import today, add_days, getdate, cint, flt, date_diff, nowdate


# Default enrichment templates by species
ENRICHMENT_TEMPLATES = {
    "Dog": [
        {"activity": "Walk", "frequency_days": 1, "duration": 30, "priority": 1},
        {"activity": "Play", "frequency_days": 1, "duration": 20, "priority": 2},
        {"activity": "Socialization", "frequency_days": 2, "duration": 15, "priority": 3},
        {"activity": "Training", "frequency_days": 2, "duration": 15, "priority": 4},
        {"activity": "Puzzle Toys", "frequency_days": 3, "duration": 20, "priority": 5},
        {"activity": "Nose Work", "frequency_days": 3, "duration": 15, "priority": 6},
    ],
    "Cat": [
        {"activity": "Cat Wand Play", "frequency_days": 1, "duration": 15, "priority": 1},
        {"activity": "Window Perch Time", "frequency_days": 1, "duration": 30, "priority": 2},
        {"activity": "Puzzle Toys", "frequency_days": 2, "duration": 20, "priority": 3},
        {"activity": "Socialization", "frequency_days": 3, "duration": 15, "priority": 4},
        {"activity": "Grooming", "frequency_days": 7, "duration": 15, "priority": 5},
    ],
}

DEFAULT_TEMPLATE = [
    {"activity": "Socialization", "frequency_days": 2, "duration": 15, "priority": 1},
    {"activity": "Play", "frequency_days": 2, "duration": 15, "priority": 2},
]


def generate_enrichment_schedule(days_ahead=7):
    """Auto-generate enrichment activities for all shelter animals.

    Creates Enrichment Activity records for the next N days based on
    species templates and individual animal needs.
    """
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_enrichment_scheduler", 0):
        return {"status": "disabled"}

    now = getdate(today())
    created_count = 0

    # Get all animals currently in shelter
    animals = frappe.get_all("Animal", filters={
        "status": ["in", ["Available for Adoption", "Under Medical Care", "Under Evaluation", "Boarding"]]
    }, fields=["name", "animal_name", "species", "temperament", "intake_date"])

    # Get available volunteers
    volunteers = frappe.get_all("Volunteer", filters={
        "status": "Active"
    }, fields=["name", "volunteer_name"])

    vol_idx = 0

    for animal in animals:
        species = animal.species or "Other"
        template = ENRICHMENT_TEMPLATES.get(species, DEFAULT_TEMPLATE)
        days_in_shelter = date_diff(now, getdate(animal.intake_date)) if animal.intake_date else 0

        # Long-stay animals get extra enrichment
        extra_activities = []
        if days_in_shelter > 30:
            extra_activities.append({"activity": "Socialization", "frequency_days": 1, "duration": 20})
        if days_in_shelter > 60:
            extra_activities.append({"activity": "Training", "frequency_days": 1, "duration": 15})

        all_activities = template + extra_activities

        for day_offset in range(days_ahead):
            target_date = add_days(now, day_offset)

            for act in all_activities:
                # Check if this activity is due on this day
                if day_offset % act["frequency_days"] != 0:
                    continue

                # Check if already scheduled
                exists = frappe.db.exists("Enrichment Activity", {
                    "animal": animal.name,
                    "activity_type": act["activity"],
                    "date": target_date,
                    "status": ["in", ["Scheduled", "Completed"]]
                })
                if exists:
                    continue

                # Assign a volunteer (round-robin)
                volunteer = None
                if volunteers:
                    volunteer = volunteers[vol_idx % len(volunteers)].name
                    vol_idx += 1

                # Create the enrichment activity
                doc = frappe.get_doc({
                    "doctype": "Enrichment Activity",
                    "animal": animal.name,
                    "activity_type": act["activity"],
                    "date": target_date,
                    "duration_minutes": act["duration"],
                    "volunteer": volunteer,
                    "status": "Scheduled"
                })
                doc.insert(ignore_permissions=True)
                created_count += 1

    frappe.db.commit()
    return {
        "status": "success",
        "activities_created": created_count,
        "animals_covered": len(animals),
        "days_scheduled": days_ahead
    }


def get_enrichment_summary(animal_name=None):
    """Get enrichment activity summary, optionally for a specific animal."""
    filters = {}
    if animal_name:
        filters["animal"] = animal_name

    # This week's activities
    week_start = add_days(today(), -getdate(today()).weekday())
    week_end = add_days(week_start, 6)

    week_activities = frappe.get_all("Enrichment Activity", filters={
        **filters,
        "date": ["between", [week_start, week_end]]
    }, fields=["status", "activity_type", "animal", "animal_name", "enjoyment_level", "date"])

    total = len(week_activities)
    completed = sum(1 for a in week_activities if a.status == "Completed")
    skipped = sum(1 for a in week_activities if a.status == "Skipped")

    # Enjoyment breakdown
    enjoyment = {}
    for a in week_activities:
        if a.enjoyment_level:
            enjoyment[a.enjoyment_level] = enjoyment.get(a.enjoyment_level, 0) + 1

    return {
        "period": f"{week_start} to {week_end}",
        "total_scheduled": total,
        "completed": completed,
        "skipped": skipped,
        "completion_rate": flt(completed / max(total, 1) * 100, 1),
        "enjoyment_breakdown": enjoyment
    }


def get_ai_enrichment_recommendation(animal_name):
    """Use AI to recommend personalized enrichment for an animal."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_enrichment_scheduler", 0):
        return {"error": "Enrichment scheduler is not enabled"}

    animal = frappe.get_doc("Animal", animal_name)

    # Get recent enrichment history
    recent = frappe.get_all("Enrichment Activity", filters={
        "animal": animal_name,
        "status": "Completed"
    }, fields=["activity_type", "enjoyment_level", "date", "notes"],
    order_by="date desc", limit_page_length=20)

    history_text = "\n".join([
        f"- {r.activity_type}: {r.enjoyment_level or 'N/A'} ({r.date}){' — ' + r.notes if r.notes else ''}"
        for r in recent
    ]) or "No enrichment history yet."

    prompt = f"""You are an animal behaviorist. Recommend enrichment activities for this shelter animal:

Species: {animal.species}
Breed: {animal.breed or 'Unknown'}
Age: {animal.estimated_age or 'Unknown'}
Temperament: {animal.temperament or 'Unknown'}
Stay Duration: Since {animal.intake_date or 'Unknown'}

Recent enrichment history:
{history_text}

Provide 5 specific enrichment recommendations with:
1. Activity name
2. Duration (minutes)
3. Frequency (times per week)
4. Why this activity benefits this particular animal
5. Any supplies needed"""

    from kennel_management.utils.ai_actions import call_llm
    response = call_llm(prompt)
    return {"recommendations": response, "animal": animal_name}
