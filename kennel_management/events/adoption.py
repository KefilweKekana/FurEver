import frappe
from frappe import _


def on_update(doc, method):
    """Handle adoption application status changes."""
    pass


def on_submit(doc, method):
    """Handle adoption application submission."""
    pass


def update_campaign_on_donation(doc, method):
    """When a Donation is created, update linked campaign stats."""
    if hasattr(doc, "campaign") and doc.campaign:
        try:
            from kennel_management.utils.campaign_builder import update_campaign_stats
            update_campaign_stats(doc.campaign)
        except Exception:
            frappe.log_error("Failed to update campaign stats on donation")
