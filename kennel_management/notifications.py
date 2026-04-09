import frappe


def get_notification_config():
    return {
        "for_doctype": {
            "Animal Admission": {"events": {"on_submit": 1}},
            "Adoption Application": {"events": {"on_change": 1}},
            "Veterinary Appointment": {"events": {"on_change": 1}},
            "Foster Application": {"events": {"on_change": 1}},
            "Lost and Found Report": {"events": {"on_change": 1}},
            "Daily Round": {"events": {"on_submit": 1}},
        },
    }
