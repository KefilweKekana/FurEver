from frappe import _
import frappe


def get_data():
    # Filter out doctypes that haven't been migrated yet
    def _safe_items(items):
        return [dt for dt in items if frappe.db.exists("DocType", dt)]

    return {
        "fieldname": "kennel_management",
        "non_standard_fieldnames": {},
        "transactions": [
            {
                "label": _("Animals"),
                "items": _safe_items(["Animal", "Kennel"]),
            },
            {
                "label": _("Intake & Adoption"),
                "items": _safe_items(["Animal Admission", "Adoption Application"]),
            },
            {
                "label": _("Medical"),
                "items": _safe_items(["Veterinary Appointment", "Veterinary Record"]),
            },
            {
                "label": _("Operations"),
                "items": _safe_items(["Daily Round", "Feeding Schedule", "Behavior Assessment"]),
            },
            {
                "label": _("CRM & Community"),
                "items": _safe_items([
                    "Volunteer",
                    "Donation",
                    "Foster Application",
                    "Lost and Found Report",
                ]),
            },
        ],
    }
