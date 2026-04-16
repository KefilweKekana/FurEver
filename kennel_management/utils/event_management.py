"""
Event Management — Feature #10
Event planning helpers, RSVP management, and post-event analytics.
"""
import frappe
from frappe.utils import today, getdate, add_days, flt, cint


def get_upcoming_events(days_ahead=30):
    """Get all upcoming shelter events."""
    events = frappe.get_all("Shelter Event", filters={
        "event_date": [">=", today()],
        "event_date": ["<=", add_days(today(), days_ahead)],
        "status": ["in", ["Planning", "Confirmed"]]
    }, fields=["name", "event_name", "event_type", "status", "event_date",
               "start_time", "end_time", "location", "max_attendees", "organizer"],
    order_by="event_date asc")

    for event in events:
        rsvp_count = frappe.db.count("Shelter Event RSVP", {
            "parent": event.name,
            "rsvp_status": ["in", ["Confirmed", "Maybe"]]
        })
        event["rsvp_count"] = rsvp_count
        event["spots_available"] = max(0, (event.max_attendees or 9999) - rsvp_count)

    return {"events": events, "total": len(events)}


def get_event_details(event_name):
    """Get full event details with RSVPs."""
    event = frappe.get_doc("Shelter Event", event_name)

    rsvps = []
    for r in event.rsvps:
        rsvps.append({
            "name": r.attendee_name,
            "email": r.email,
            "phone": r.phone,
            "status": r.rsvp_status,
            "guests": r.guests
        })

    confirmed = sum(1 for r in rsvps if r["status"] == "Confirmed")
    total_attending = confirmed + sum(r["guests"] for r in rsvps if r["status"] == "Confirmed")

    return {
        "event": {
            "name": event.name,
            "event_name": event.event_name,
            "event_type": event.event_type,
            "status": event.status,
            "event_date": str(event.event_date),
            "start_time": str(event.start_time) if event.start_time else None,
            "end_time": str(event.end_time) if event.end_time else None,
            "location": event.location,
            "description": event.description,
            "max_attendees": event.max_attendees,
            "campaign": event.campaign
        },
        "rsvps": rsvps,
        "confirmed_count": confirmed,
        "total_attending": total_attending,
        "spots_remaining": max(0, (event.max_attendees or 9999) - total_attending)
    }


def add_rsvp(event_name, attendee_name, email, phone=None, guests=0):
    """Add an RSVP to an event."""
    event = frappe.get_doc("Shelter Event", event_name)

    # Check capacity
    current = sum(1 + (r.guests or 0) for r in event.rsvps if r.rsvp_status in ["Confirmed", "Maybe"])
    needed = 1 + cint(guests)
    max_att = event.max_attendees or 0

    if max_att > 0 and current + needed > max_att:
        return {"status": "error", "message": "Event is at full capacity"}

    # Check for duplicate
    for r in event.rsvps:
        if r.email and r.email.lower() == (email or "").lower():
            return {"status": "error", "message": "Already RSVP'd with this email"}

    event.append("rsvps", {
        "attendee_name": attendee_name,
        "email": email,
        "phone": phone,
        "rsvp_status": "Confirmed",
        "guests": cint(guests)
    })
    event.save(ignore_permissions=True)
    frappe.db.commit()

    # Send confirmation email
    if email:
        _send_rsvp_confirmation(email, attendee_name, event)

    return {"status": "success", "message": f"RSVP confirmed for {attendee_name}"}


def _send_rsvp_confirmation(email, name, event):
    """Send RSVP confirmation email."""
    try:
        frappe.sendmail(
            recipients=[email],
            subject=f"✅ RSVP Confirmed: {event.event_name}",
            message=f"""
            <h2>RSVP Confirmed!</h2>
            <p>Dear {name},</p>
            <p>Your RSVP for <strong>{event.event_name}</strong> has been confirmed.</p>
            <p><strong>Date:</strong> {event.event_date}<br>
            <strong>Time:</strong> {event.start_time or 'TBA'} — {event.end_time or 'TBA'}<br>
            <strong>Location:</strong> {event.location or 'TBA'}</p>
            <p>We look forward to seeing you there!</p>
            """,
            now=True
        )
    except Exception:
        frappe.log_error(f"Failed to send RSVP confirmation to {email}")


def get_event_analytics():
    """Get analytics across all completed events."""
    completed = frappe.get_all("Shelter Event", filters={
        "status": "Completed"
    }, fields=["name", "event_name", "event_type", "event_date",
               "attendee_count", "animals_adopted", "donations_collected"])

    total_events = len(completed)
    total_attendees = sum(cint(e.attendee_count) for e in completed)
    total_adoptions = sum(cint(e.animals_adopted) for e in completed)
    total_donations = sum(flt(e.donations_collected) for e in completed)

    # Breakdown by type
    by_type = {}
    for e in completed:
        t = e.event_type or "Other"
        if t not in by_type:
            by_type[t] = {"count": 0, "attendees": 0, "adoptions": 0, "donations": 0}
        by_type[t]["count"] += 1
        by_type[t]["attendees"] += cint(e.attendee_count)
        by_type[t]["adoptions"] += cint(e.animals_adopted)
        by_type[t]["donations"] += flt(e.donations_collected)

    return {
        "total_events": total_events,
        "total_attendees": total_attendees,
        "total_adoptions": total_adoptions,
        "total_donations": total_donations,
        "avg_attendees": flt(total_attendees / max(total_events, 1), 1),
        "by_type": by_type,
        "events": completed
    }


def generate_event_promo(event_name):
    """Use AI to generate promotional material for an event."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_event_management", 0):
        return {"error": "Event management feature is not enabled"}

    event = frappe.get_doc("Shelter Event", event_name)

    prompt = f"""You are an event marketing specialist for an animal shelter. Create promotional material:

Event: {event.event_name}
Type: {event.event_type}
Date: {event.event_date}
Time: {event.start_time or 'TBA'} - {event.end_time or 'TBA'}
Location: {event.location or 'TBA'}
Description: {event.description or 'No description yet'}

Create:
1. A catchy event tagline (under 10 words)
2. A social media post (280 characters max)
3. An email invitation (150 words)
4. Key talking points for volunteers to share
5. Suggested activities/agenda items for this event type"""

    from kennel_management.utils.ai_actions import call_llm
    response = call_llm(prompt)
    return {"promo": response, "event": event_name}
