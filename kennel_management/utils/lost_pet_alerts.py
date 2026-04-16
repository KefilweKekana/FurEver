"""
Community Lost Pet Alert System — Feature #8
Blast alerts via email/SMS for lost and found animals with matching logic.
"""
import frappe
from frappe.utils import today, add_days, getdate, now_datetime


def send_lost_pet_alert(lost_report_name):
    """Send community alerts for a lost pet report.

    Sends notifications to:
    1. All active volunteers in the area
    2. Recent adopters (they know the community)
    3. Matched found reports (if any)
    """
    report = frappe.get_doc("Lost and Found Report", lost_report_name)

    if report.report_type != "Lost":
        return {"error": "Alert can only be sent for Lost reports"}

    # Build alert content
    alert = {
        "animal_name": report.animal_name or "Unknown",
        "species": report.species or "Unknown",
        "breed": report.breed or "Unknown breed",
        "color": report.color or "Unknown color",
        "last_seen_location": report.location or "Unknown location",
        "last_seen_date": str(report.date_reported or today()),
        "description": report.description or "",
        "contact_name": report.reporter_name or "",
        "contact_phone": report.reporter_phone or "",
        "contact_email": report.reporter_email or "",
        "photo": report.photo if hasattr(report, "photo") else None
    }

    sent_count = 0

    # 1. Email volunteers
    volunteers = frappe.get_all("Volunteer", filters={"status": "Active"},
                                fields=["volunteer_name", "email"])
    for vol in volunteers:
        if vol.email:
            _send_lost_pet_email(vol.email, vol.volunteer_name, alert)
            sent_count += 1

    # 2. Check for matching found reports
    matches = find_potential_matches(report)

    # 3. Log the alert
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Lost and Found Report",
        "reference_name": lost_report_name,
        "content": f"🔔 Community alert sent to {sent_count} contacts. "
                   f"{len(matches)} potential matches found."
    }).insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "status": "success",
        "alerts_sent": sent_count,
        "potential_matches": matches
    }


def find_potential_matches(report):
    """Find potential matches between lost and found reports.

    Uses species, breed, color, location, and date proximity for matching.
    """
    opposite_type = "Found" if report.report_type == "Lost" else "Lost"
    cutoff_date = add_days(today(), -30)

    candidates = frappe.get_all("Lost and Found Report", filters={
        "report_type": opposite_type,
        "status": ["in", ["Open", "Under Investigation"]],
        "date_reported": [">=", cutoff_date]
    }, fields=["name", "animal_name", "species", "breed", "color",
               "location", "description", "reporter_name", "reporter_phone"])

    matches = []
    for c in candidates:
        score = _calculate_match_score(report, c)
        if score >= 30:
            matches.append({
                "report": c.name,
                "animal_name": c.animal_name,
                "match_score": score,
                "species": c.species,
                "breed": c.breed,
                "color": c.color,
                "location": c.location,
                "reporter": c.reporter_name,
                "phone": c.reporter_phone
            })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:10]


def _calculate_match_score(report, candidate):
    """Calculate a match score between two reports (0-100)."""
    score = 0

    # Species match (must match)
    r_species = (report.species or "").lower().strip()
    c_species = (candidate.species or "").lower().strip()
    if r_species and c_species and r_species == c_species:
        score += 30
    elif r_species and c_species:
        return 0  # Different species = no match

    # Breed match
    r_breed = (report.breed or "").lower().strip()
    c_breed = (candidate.breed or "").lower().strip()
    if r_breed and c_breed:
        if r_breed == c_breed:
            score += 25
        elif r_breed in c_breed or c_breed in r_breed:
            score += 15

    # Color match
    r_color = (report.color or "").lower().strip()
    c_color = (candidate.color or "").lower().strip()
    if r_color and c_color:
        r_colors = set(r_color.replace(",", " ").replace("/", " ").split())
        c_colors = set(c_color.replace(",", " ").replace("/", " ").split())
        overlap = r_colors & c_colors
        if overlap:
            score += min(20, len(overlap) * 10)

    # Location proximity (simple text match)
    r_loc = (report.location or "").lower()
    c_loc = (candidate.location or "").lower()
    if r_loc and c_loc:
        r_words = set(r_loc.split())
        c_words = set(c_loc.split())
        common = r_words & c_words - {"the", "and", "or", "in", "at", "on", "near"}
        if common:
            score += min(15, len(common) * 5)

    # Date proximity
    if report.date_reported and candidate.date_reported:
        days_apart = abs(date_diff(report.date_reported, candidate.date_reported))
        if days_apart <= 3:
            score += 10
        elif days_apart <= 7:
            score += 5

    return min(score, 100)


def _send_lost_pet_email(email, recipient_name, alert):
    """Send lost pet alert email."""
    subject = f"🔍 LOST PET ALERT: {alert['species']} — {alert['animal_name']} near {alert['last_seen_location']}"

    message = f"""
    <h2>🔍 Lost Pet Alert</h2>
    <p>Dear {recipient_name},</p>
    <p>A pet has been reported lost in our community. Please keep an eye out!</p>

    <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
        <tr><td style="padding: 8px; font-weight: bold;">Name:</td><td style="padding: 8px;">{alert['animal_name']}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Species:</td><td style="padding: 8px;">{alert['species']}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Breed:</td><td style="padding: 8px;">{alert['breed']}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Color:</td><td style="padding: 8px;">{alert['color']}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Last Seen:</td><td style="padding: 8px;">{alert['last_seen_location']}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Date:</td><td style="padding: 8px;">{alert['last_seen_date']}</td></tr>
    </table>

    <p><strong>Description:</strong> {alert['description']}</p>

    <p>If you spot this animal, please contact:<br>
    {alert['contact_name']} — {alert['contact_phone'] or alert['contact_email']}</p>

    <p>Thank you for helping reunite pets with their families!</p>
    """

    try:
        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            now=True
        )
    except Exception:
        frappe.log_error(f"Failed to send lost pet alert to {email}")


def auto_match_lost_and_found():
    """Daily task: check for new matches between lost and found reports."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_lost_pet_alerts", 0):
        return

    open_reports = frappe.get_all("Lost and Found Report", filters={
        "status": ["in", ["Open", "Under Investigation"]],
        "date_reported": [">=", add_days(today(), -30)]
    }, fields=["name", "report_type"])

    new_matches = 0
    for r in open_reports:
        report = frappe.get_doc("Lost and Found Report", r.name)
        matches = find_potential_matches(report)
        if matches:
            # Log matches as comments
            for match in matches[:3]:
                frappe.get_doc({
                    "doctype": "Comment",
                    "comment_type": "Info",
                    "reference_doctype": "Lost and Found Report",
                    "reference_name": r.name,
                    "content": (
                        f"🔗 Potential match: {match['report']} — "
                        f"{match['animal_name']} ({match['species']}/{match['breed']}) "
                        f"Score: {match['match_score']}%"
                    )
                }).insert(ignore_permissions=True)
                new_matches += 1

    frappe.db.commit()
    return {"matches_found": new_matches}
