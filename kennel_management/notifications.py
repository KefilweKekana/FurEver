import frappe


def get_notification_config():
    # Build notification config, skipping any doctypes that haven't been migrated yet
    all_doctypes = {
        "Animal Admission": {"status": ["in", ["Draft", "Processing"]]},
        "Adoption Application": {"status": ["in", ["Pending", "Under Review", "Home Check Scheduled"]]},
        "Veterinary Appointment": {"status": ["in", ["Scheduled", "Checked In", "In Progress"]]},
        "Foster Application": {"status": ["in", ["Pending"]]},
        "Lost and Found Report": {"status": ["in", ["Open", "Investigating"]]},
        "Daily Round": {"status": ["in", ["Draft", "In Progress"]]},
    }

    for_doctype = {}
    for dt, filters in all_doctypes.items():
        try:
            if frappe.db.exists("DocType", dt):
                for_doctype[dt] = filters
        except Exception:
            pass

    return {
        "for_doctype": for_doctype,
    }
