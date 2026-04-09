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
