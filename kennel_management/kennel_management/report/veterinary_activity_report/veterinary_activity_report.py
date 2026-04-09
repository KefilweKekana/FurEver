import frappe
from frappe.utils import today, getdate, add_months, flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(filters)
    report_summary = get_summary(filters)

    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"fieldname": "name", "label": "Appointment", "fieldtype": "Link", "options": "Veterinary Appointment", "width": 160},
        {"fieldname": "animal_name", "label": "Animal", "fieldtype": "Data", "width": 140},
        {"fieldname": "species", "label": "Species", "fieldtype": "Data", "width": 90},
        {"fieldname": "appointment_type", "label": "Type", "fieldtype": "Data", "width": 150},
        {"fieldname": "appointment_date", "label": "Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "veterinarian", "label": "Vet", "fieldtype": "Data", "width": 140},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 110},
        {"fieldname": "priority", "label": "Priority", "fieldtype": "Data", "width": 90},
        {"fieldname": "total_cost", "label": "Cost (R)", "fieldtype": "Currency", "width": 100},
        {"fieldname": "followup_required", "label": "Follow-up?", "fieldtype": "Check", "width": 80},
    ]


def get_data(filters):
    conditions = {}

    if filters.get("from_date"):
        conditions["appointment_date"] = [">=", filters["from_date"]]
    if filters.get("to_date"):
        if "appointment_date" in conditions:
            conditions["appointment_date"] = ["between", [filters["from_date"], filters["to_date"]]]
        else:
            conditions["appointment_date"] = ["<=", filters["to_date"]]
    if filters.get("appointment_type"):
        conditions["appointment_type"] = filters["appointment_type"]
    if filters.get("veterinarian"):
        conditions["veterinarian"] = filters["veterinarian"]
    if filters.get("status"):
        conditions["status"] = filters["status"]

    return frappe.get_all("Veterinary Appointment",
        filters=conditions,
        fields=[
            "name", "animal_name", "species", "appointment_type",
            "appointment_date", "veterinarian", "status", "priority",
            "total_cost", "followup_required"
        ],
        order_by="appointment_date desc",
        limit_page_length=500,
    )


def get_chart(filters):
    # Appointment types breakdown
    type_data = frappe.db.sql("""
        SELECT appointment_type, COUNT(*) as count
        FROM `tabVeterinary Appointment`
        WHERE docstatus < 2
        GROUP BY appointment_type
        ORDER BY count DESC
        LIMIT 10
    """, as_dict=True)

    if not type_data:
        return None

    return {
        "data": {
            "labels": [t.appointment_type for t in type_data],
            "datasets": [{"values": [t.count for t in type_data]}],
        },
        "type": "bar",
        "colors": ["#2980b9"],
    }


def get_summary(filters):
    total = frappe.db.count("Veterinary Appointment", {"docstatus": ["<", 2]})
    completed = frappe.db.count("Veterinary Appointment", {"status": "Completed"})
    scheduled = frappe.db.count("Veterinary Appointment", {
        "status": "Scheduled",
        "appointment_date": [">=", today()]
    })
    emergencies = frappe.db.count("Veterinary Appointment", {
        "priority": "Emergency",
        "docstatus": ["<", 2]
    })

    total_cost = frappe.db.sql("""
        SELECT COALESCE(SUM(total_cost), 0) FROM `tabVeterinary Appointment`
        WHERE status = 'Completed'
    """)[0][0]

    return [
        {"value": total, "label": "Total Appointments", "indicator": "Blue", "datatype": "Int"},
        {"value": completed, "label": "Completed", "indicator": "Green", "datatype": "Int"},
        {"value": scheduled, "label": "Upcoming", "indicator": "Orange", "datatype": "Int"},
        {"value": emergencies, "label": "Emergencies", "indicator": "Red", "datatype": "Int"},
        {"value": total_cost, "label": "Total Vet Costs", "indicator": "Blue", "datatype": "Currency"},
    ]
