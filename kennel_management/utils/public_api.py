"""
Public API & Webhook System — Feature #15
REST API helpers, webhook dispatch, and API key management.
"""
import frappe
import json
import hashlib
import hmac
from frappe.utils import now_datetime, cint


def dispatch_webhook(event_type, payload):
    """Dispatch a webhook to all registered endpoints for an event type.

    Args:
        event_type: str — e.g., 'animal.created', 'adoption.approved', 'donation.received'
        payload: dict — the event data to send
    """
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_public_api", 0):
        return

    # Get all active webhook subscriptions
    webhooks = frappe.get_all("Webhook", filters={
        "webhook_doctype": event_type.split(".")[0].title() if "." in event_type else "",
        "enabled": 1
    }, fields=["name", "request_url", "webhook_secret"])

    results = []
    for wh in webhooks:
        result = _send_webhook(wh, event_type, payload)
        results.append(result)

    return {"dispatched": len(results), "results": results}


def _send_webhook(webhook, event_type, payload):
    """Send a single webhook request."""
    import requests

    body = json.dumps({
        "event": event_type,
        "timestamp": str(now_datetime()),
        "data": payload
    }, default=str)

    headers = {
        "Content-Type": "application/json",
        "X-Kennel-Event": event_type,
        "X-Kennel-Timestamp": str(now_datetime())
    }

    # Sign the payload if secret exists
    if webhook.webhook_secret:
        signature = hmac.new(
            webhook.webhook_secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        headers["X-Kennel-Signature"] = f"sha256={signature}"

    try:
        resp = requests.post(
            webhook.request_url,
            data=body,
            headers=headers,
            timeout=10
        )
        return {
            "webhook": webhook.name,
            "url": webhook.request_url,
            "status_code": resp.status_code,
            "success": resp.status_code < 400
        }
    except Exception as e:
        frappe.log_error(f"Webhook delivery failed: {webhook.request_url} — {str(e)}")
        return {
            "webhook": webhook.name,
            "url": webhook.request_url,
            "status_code": 0,
            "success": False,
            "error": str(e)
        }


def get_public_animals(species=None, status=None, limit=20, offset=0):
    """Public API: Get available animals with limited fields (no auth required).

    Returns only adoption-safe public information.
    """
    filters = {"status": "Available for Adoption"}
    if species:
        filters["species"] = species

    animals = frappe.get_all("Animal", filters=filters,
        fields=["name", "animal_name", "species", "breed", "color",
                "sex", "estimated_age", "weight", "temperament",
                "good_with_children", "good_with_dogs", "good_with_cats",
                "photo", "special_notes", "intake_date"],
        order_by="intake_date desc",
        limit_page_length=cint(limit),
        limit_start=cint(offset))

    total = frappe.db.count("Animal", filters)

    return {
        "animals": animals,
        "total": total,
        "limit": cint(limit),
        "offset": cint(offset),
        "has_more": (cint(offset) + cint(limit)) < total
    }


def get_public_events(upcoming_only=True, limit=10):
    """Public API: Get upcoming shelter events."""
    filters = {}
    if upcoming_only:
        filters["event_date"] = [">=", frappe.utils.today()]
        filters["status"] = ["in", ["Planning", "Confirmed"]]

    events = frappe.get_all("Shelter Event", filters=filters,
        fields=["name", "event_name", "event_type", "event_date",
                "start_time", "end_time", "location", "description", "max_attendees"],
        order_by="event_date asc",
        limit_page_length=cint(limit))

    return {"events": events, "total": len(events)}


def get_public_campaigns(active_only=True, limit=10):
    """Public API: Get active donation campaigns."""
    filters = {}
    if active_only:
        filters["status"] = "Active"

    campaigns = frappe.get_all("Donation Campaign", filters=filters,
        fields=["name", "campaign_name", "campaign_type", "goal_amount",
                "amount_raised", "progress_percent", "story", "cover_image",
                "start_date", "end_date"],
        order_by="start_date desc",
        limit_page_length=cint(limit))

    return {"campaigns": campaigns, "total": len(campaigns)}


def get_api_stats():
    """Get API usage statistics."""
    return {
        "available_endpoints": [
            {"path": "/api/method/kennel_management.api.public_animals", "method": "GET", "auth": False},
            {"path": "/api/method/kennel_management.api.public_events", "method": "GET", "auth": False},
            {"path": "/api/method/kennel_management.api.public_campaigns", "method": "GET", "auth": False},
            {"path": "/api/method/kennel_management.api.rsvp_event", "method": "POST", "auth": False},
            {"path": "/api/method/kennel_management.api.submit_adoption_survey", "method": "POST", "auth": False},
            {"path": "/api/method/kennel_management.api.get_capacity_forecast", "method": "GET", "auth": True},
            {"path": "/api/method/kennel_management.api.get_medical_timeline", "method": "GET", "auth": True},
            {"path": "/api/method/kennel_management.api.get_network_overview", "method": "GET", "auth": True},
        ],
        "webhook_events": [
            "animal.created", "animal.updated", "animal.status_changed",
            "adoption.submitted", "adoption.approved", "adoption.rejected",
            "donation.received", "event.created", "survey.completed",
            "transfer.initiated", "transfer.completed"
        ]
    }
