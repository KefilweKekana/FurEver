// Copyright (c) 2024, SPCA and contributors
// For license information, please see license.txt

frappe.query_reports["Veterinary Activity Report"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
        },
        {
            "fieldname": "appointment_type",
            "label": __("Appointment Type"),
            "fieldtype": "Select",
            "options": "\nIntake Examination\nWellness Check\nVaccination\nSpay-Neuter\nSurgery\nDental\nEmergency\nFollow-up\nBehavior Consultation\nLab Work\nX-Ray\nEuthanasia Evaluation\nMicrochipping",
        },
        {
            "fieldname": "veterinarian",
            "label": __("Veterinarian"),
            "fieldtype": "Link",
            "options": "User",
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nScheduled\nChecked In\nIn Progress\nCompleted\nCancelled\nNo Show\nRescheduled",
        },
    ],
};
