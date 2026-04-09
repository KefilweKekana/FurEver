import frappe
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    report_summary = get_summary(data)

    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"fieldname": "kennel_name", "label": "Kennel", "fieldtype": "Link", "options": "Kennel", "width": 180},
        {"fieldname": "kennel_type", "label": "Type", "fieldtype": "Data", "width": 120},
        {"fieldname": "section", "label": "Section", "fieldtype": "Data", "width": 120},
        {"fieldname": "building", "label": "Building", "fieldtype": "Data", "width": 120},
        {"fieldname": "capacity", "label": "Capacity", "fieldtype": "Int", "width": 90},
        {"fieldname": "current_occupancy", "label": "Occupied", "fieldtype": "Int", "width": 90},
        {"fieldname": "available_spaces", "label": "Available", "fieldtype": "Int", "width": 90},
        {"fieldname": "occupancy_pct", "label": "Occupancy %", "fieldtype": "Percent", "width": 110},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
        {"fieldname": "size_category", "label": "Size Category", "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    kennels = frappe.get_all("Kennel",
        fields=[
            "name as kennel_name", "kennel_type", "section", "building",
            "capacity", "current_occupancy", "status", "size_category"
        ],
        order_by="kennel_name",
    )

    for k in kennels:
        k["available_spaces"] = max(0, (k.capacity or 0) - (k.current_occupancy or 0))
        if k.capacity:
            k["occupancy_pct"] = round((k.current_occupancy or 0) / k.capacity * 100, 1)
        else:
            k["occupancy_pct"] = 0

    return kennels


def get_chart(data):
    if not data:
        return None

    labels = [d["kennel_name"] for d in data if d.get("status") == "Active"]
    occupied = [d["current_occupancy"] or 0 for d in data if d.get("status") == "Active"]
    available = [d["available_spaces"] or 0 for d in data if d.get("status") == "Active"]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Occupied", "values": occupied},
                {"name": "Available", "values": available},
            ],
        },
        "type": "bar",
        "barOptions": {"stacked": 1},
        "colors": ["#e74c3c", "#27ae60"],
    }


def get_summary(data):
    total_capacity = sum(d.get("capacity", 0) or 0 for d in data)
    total_occupied = sum(d.get("current_occupancy", 0) or 0 for d in data)
    total_available = total_capacity - total_occupied
    overall_pct = round(total_occupied / total_capacity * 100, 1) if total_capacity else 0
    full_kennels = sum(1 for d in data if d.get("occupancy_pct", 0) >= 100)

    indicator = "Green" if overall_pct < 70 else ("Orange" if overall_pct < 90 else "Red")

    return [
        {"value": total_capacity, "label": "Total Capacity", "indicator": "Blue", "datatype": "Int"},
        {"value": total_occupied, "label": "Total Occupied", "indicator": indicator, "datatype": "Int"},
        {"value": total_available, "label": "Available Spaces", "indicator": "Green", "datatype": "Int"},
        {"value": overall_pct, "label": "Overall Occupancy %", "indicator": indicator, "datatype": "Percent"},
        {"value": full_kennels, "label": "Full Kennels", "indicator": "Red" if full_kennels else "Green", "datatype": "Int"},
    ]
