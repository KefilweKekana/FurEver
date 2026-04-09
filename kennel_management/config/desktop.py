from frappe import _


def get_data():
    return {
        "fieldname": "kennel_management",
        "non_standard_fieldnames": {},
        "transactions": [
            {
                "label": _("Animals"),
                "items": ["Animal", "Kennel"],
            },
            {
                "label": _("Intake & Adoption"),
                "items": ["Animal Admission", "Adoption Application"],
            },
            {
                "label": _("Medical"),
                "items": ["Veterinary Appointment", "Veterinary Record"],
            },
            {
                "label": _("Operations"),
                "items": ["Daily Round", "Feeding Schedule", "Behavior Assessment"],
            },
            {
                "label": _("CRM & Community"),
                "items": [
                    "Volunteer",
                    "Donation",
                    "Foster Application",
                    "Lost and Found Report",
                ],
            },
        ],
    }
