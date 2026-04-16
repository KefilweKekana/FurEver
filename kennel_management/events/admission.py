import frappe
from frappe import _


def on_submit(doc, method):
    """Handle admission submission."""
    frappe.publish_realtime(
        "new_admission",
        {"admission": doc.name, "animal_name": doc.animal_name_field},
        after_commit=True,
    )


def on_cancel(doc, method):
    pass


def auto_match_lost_found_on_intake(doc, method):
    """When a new animal is admitted, check against open lost reports.

    If a high-confidence match is found, create an urgent ToDo so staff
    can investigate a potential owner reunification immediately.
    """
    try:
        from kennel_management.utils.ai_matching import auto_match_on_admission
        auto_match_on_admission(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Lost/Found Auto-Match on Admission")
