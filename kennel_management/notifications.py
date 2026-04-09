import frappe


def get_notification_config():
    return {
        "for_doctype": {
            "Animal Admission": {"status": ["in", ["Draft", "Processing"]]},
            "Adoption Application": {"status": ["in", ["Pending", "Under Review", "Home Check Scheduled"]]},
            "Veterinary Appointment": {"status": ["in", ["Scheduled", "Checked In", "In Progress"]]},
            "Foster Application": {"status": ["in", ["Pending"]]},
            "Lost and Found Report": {"status": ["in", ["Open", "Investigating"]]},
            "Daily Round": {"status": ["in", ["Draft", "In Progress"]]},
        },
    }
