import frappe
from frappe.utils import today, getdate, add_months


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(filters)
    report_summary = get_summary(filters)

    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"fieldname": "name", "label": "Application", "fieldtype": "Link", "options": "Adoption Application", "width": 160},
        {"fieldname": "applicant_name", "label": "Applicant", "fieldtype": "Data", "width": 180},
        {"fieldname": "animal_name", "label": "Animal", "fieldtype": "Data", "width": 140},
        {"fieldname": "species_preference", "label": "Species", "fieldtype": "Data", "width": 100},
        {"fieldname": "application_date", "label": "Applied On", "fieldtype": "Date", "width": 120},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 150},
        {"fieldname": "adoption_date", "label": "Adopted On", "fieldtype": "Date", "width": 120},
        {"fieldname": "adoption_fee", "label": "Fee (R)", "fieldtype": "Currency", "width": 100},
        {"fieldname": "source_channel", "label": "Source", "fieldtype": "Data", "width": 120},
        {"fieldname": "days_to_adopt", "label": "Days to Adopt", "fieldtype": "Int", "width": 100},
    ]


def get_data(filters):
    conditions = {}

    if filters.get("from_date"):
        conditions["application_date"] = [">=", filters["from_date"]]
    if filters.get("to_date"):
        if "application_date" in conditions:
            conditions["application_date"] = ["between", [filters["from_date"], filters["to_date"]]]
        else:
            conditions["application_date"] = ["<=", filters["to_date"]]
    if filters.get("status"):
        conditions["status"] = filters["status"]

    applications = frappe.get_all("Adoption Application",
        filters=conditions,
        fields=[
            "name", "applicant_name", "animal_name", "species_preference",
            "application_date", "status", "adoption_date", "adoption_fee",
            "source_channel"
        ],
        order_by="application_date desc",
        limit_page_length=500,
    )

    for app in applications:
        if app.adoption_date and app.application_date:
            app["days_to_adopt"] = (getdate(app.adoption_date) - getdate(app.application_date)).days
        else:
            app["days_to_adopt"] = None

    return applications


def get_chart(filters):
    # Status distribution pie chart
    status_data = frappe.db.sql("""
        SELECT status, COUNT(*) as count
        FROM `tabAdoption Application`
        WHERE docstatus < 2
        GROUP BY status
        ORDER BY count DESC
    """, as_dict=True)

    if not status_data:
        return None

    return {
        "data": {
            "labels": [s.status for s in status_data],
            "datasets": [{"values": [s.count for s in status_data]}],
        },
        "type": "pie",
        "colors": ["#3498db", "#e67e22", "#f39c12", "#2ecc71", "#27ae60", "#e74c3c", "#95a5a6", "#8e44ad"],
    }


def get_summary(filters):
    total = frappe.db.count("Adoption Application", {"docstatus": ["<", 2]})
    completed = frappe.db.count("Adoption Application", {"status": "Adoption Completed"})
    pending = frappe.db.count("Adoption Application", {"status": ["in", ["Pending", "Under Review"]]})
    approved = frappe.db.count("Adoption Application", {"status": "Approved"})

    total_fees = frappe.db.sql("""
        SELECT COALESCE(SUM(adoption_fee), 0) FROM `tabAdoption Application`
        WHERE status = 'Adoption Completed' AND adoption_fee_paid = 1
    """)[0][0]

    return [
        {"value": total, "label": "Total Applications", "indicator": "Blue", "datatype": "Int"},
        {"value": pending, "label": "Pending Review", "indicator": "Orange", "datatype": "Int"},
        {"value": approved, "label": "Approved", "indicator": "Green", "datatype": "Int"},
        {"value": completed, "label": "Completed", "indicator": "Green", "datatype": "Int"},
        {"value": total_fees, "label": "Total Fees Collected", "indicator": "Blue", "datatype": "Currency"},
    ]
