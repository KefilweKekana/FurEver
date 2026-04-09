// Copyright (c) 2024, SPCA and contributors
// For license information, please see license.txt

frappe.query_reports["Adoption Report"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -3),
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nPending\nUnder Review\nHome Check Scheduled\nHome Check Completed\nApproved\nAdoption Completed\nRejected\nWithdrawn\nWaitlisted",
        },
    ],
};
