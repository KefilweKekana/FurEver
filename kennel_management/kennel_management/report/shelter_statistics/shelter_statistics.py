import frappe
from frappe.utils import today, add_days, getdate, flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(filters)
    report_summary = get_report_summary()

    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"fieldname": "metric", "label": "Metric", "fieldtype": "Data", "width": 300},
        {"fieldname": "value", "label": "Value", "fieldtype": "Data", "width": 150},
        {"fieldname": "category", "label": "Category", "fieldtype": "Data", "width": 150},
    ]


def get_data(filters):
    data = []

    # --- Animal Census ---
    total_animals = frappe.db.count("Animal", filters={
        "status": ["not in", ["Adopted", "Transferred", "Deceased"]]
    })
    available = frappe.db.count("Animal", filters={"status": "Available for Adoption"})
    medical_hold = frappe.db.count("Animal", filters={"status": "Medical Hold"})
    behavior_hold = frappe.db.count("Animal", filters={"status": "Behavior Hold"})
    quarantine = frappe.db.count("Animal", filters={"status": "Quarantine"})
    stray_hold = frappe.db.count("Animal", filters={"status": "Stray Hold"})
    in_foster = frappe.db.count("Animal", filters={"status": "In Foster Care"})
    in_treatment = frappe.db.count("Animal", filters={"status": "In Treatment"})
    reserved = frappe.db.count("Animal", filters={"status": "Reserved"})

    data.append({"metric": "Total Animals in Shelter", "value": total_animals, "category": "Census"})
    data.append({"metric": "Available for Adoption", "value": available, "category": "Census"})
    data.append({"metric": "In Foster Care", "value": in_foster, "category": "Census"})
    data.append({"metric": "Medical Hold", "value": medical_hold, "category": "Census"})
    data.append({"metric": "Behavior Hold", "value": behavior_hold, "category": "Census"})
    data.append({"metric": "Quarantine", "value": quarantine, "category": "Census"})
    data.append({"metric": "Stray Hold", "value": stray_hold, "category": "Census"})
    data.append({"metric": "In Treatment", "value": in_treatment, "category": "Census"})
    data.append({"metric": "Reserved", "value": reserved, "category": "Census"})

    # --- Species Breakdown ---
    species_data = frappe.db.sql("""
        SELECT species, COUNT(*) as count
        FROM `tabAnimal`
        WHERE status NOT IN ('Adopted', 'Transferred', 'Deceased')
        GROUP BY species
        ORDER BY count DESC
    """, as_dict=True)
    for s in species_data:
        data.append({"metric": f"  {s.species or 'Unknown'}", "value": s.count, "category": "By Species"})

    # --- Kennel Occupancy ---
    kennels = frappe.db.sql("""
        SELECT kennel_name, current_occupancy, capacity, status
        FROM `tabKennel`
        WHERE status = 'Active'
        ORDER BY kennel_name
    """, as_dict=True)
    total_capacity = 0
    total_occupancy = 0
    for k in kennels:
        total_capacity += (k.capacity or 0)
        total_occupancy += (k.current_occupancy or 0)

    if total_capacity:
        occupancy_pct = round((total_occupancy / total_capacity) * 100, 1)
    else:
        occupancy_pct = 0

    data.append({"metric": "Total Kennel Capacity", "value": total_capacity, "category": "Kennels"})
    data.append({"metric": "Current Occupancy", "value": total_occupancy, "category": "Kennels"})
    data.append({"metric": "Occupancy Rate", "value": f"{occupancy_pct}%", "category": "Kennels"})

    # --- This Month Activity ---
    from_date = getdate(today()).replace(day=1)
    to_date = today()

    month_admissions = frappe.db.count("Animal Admission", filters={
        "admission_date": ["between", [from_date, to_date]],
        "docstatus": 1,
    })
    month_adoptions = frappe.db.count("Adoption Application", filters={
        "adoption_date": ["between", [from_date, to_date]],
        "status": "Adoption Completed",
    })
    month_vet = frappe.db.count("Veterinary Appointment", filters={
        "appointment_date": ["between", [from_date, to_date]],
        "docstatus": 1,
    })
    month_donations = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM `tabDonation`
        WHERE donation_date BETWEEN %s AND %s AND docstatus = 1
    """, (from_date, to_date))[0][0]

    data.append({"metric": "Admissions This Month", "value": month_admissions, "category": "Monthly Activity"})
    data.append({"metric": "Adoptions This Month", "value": month_adoptions, "category": "Monthly Activity"})
    data.append({"metric": "Vet Appointments This Month", "value": month_vet, "category": "Monthly Activity"})
    data.append({"metric": "Donations This Month", "value": f"R {flt(month_donations, 2):,.2f}", "category": "Monthly Activity"})

    # --- Pending Items ---
    pending_apps = frappe.db.count("Adoption Application", filters={
        "status": ["in", ["Pending", "Under Review"]]
    })
    pending_vet = frappe.db.count("Veterinary Appointment", filters={
        "status": "Scheduled",
        "appointment_date": [">=", today()],
    })
    overdue_followups = frappe.db.count("Veterinary Appointment", filters={
        "followup_required": 1,
        "followup_date": ["<", today()],
        "status": "Completed",
    })

    data.append({"metric": "Pending Adoption Applications", "value": pending_apps, "category": "Pending"})
    data.append({"metric": "Upcoming Vet Appointments", "value": pending_vet, "category": "Pending"})
    data.append({"metric": "Overdue Follow-ups", "value": overdue_followups, "category": "Pending"})

    return data


def get_chart_data(filters):
    # Admissions vs Adoptions over last 6 months
    from frappe.utils import add_months
    labels = []
    admissions = []
    adoptions_data = []

    for i in range(5, -1, -1):
        month_start = add_months(getdate(today()).replace(day=1), -i)
        if i > 0:
            month_end = add_days(add_months(month_start, 1), -1)
        else:
            month_end = today()

        labels.append(month_start.strftime("%b %Y"))

        adm_count = frappe.db.count("Animal Admission", filters={
            "admission_date": ["between", [month_start, month_end]],
            "docstatus": 1,
        })
        adopt_count = frappe.db.count("Adoption Application", filters={
            "adoption_date": ["between", [month_start, month_end]],
            "status": "Adoption Completed",
        })

        admissions.append(adm_count)
        adoptions_data.append(adopt_count)

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Admissions", "values": admissions},
                {"name": "Adoptions", "values": adoptions_data},
            ],
        },
        "type": "bar",
        "colors": ["#e74c3c", "#27ae60"],
    }


def get_report_summary():
    total = frappe.db.count("Animal", filters={
        "status": ["not in", ["Adopted", "Transferred", "Deceased"]]
    })
    available = frappe.db.count("Animal", filters={"status": "Available for Adoption"})
    pending = frappe.db.count("Adoption Application", filters={
        "status": ["in", ["Pending", "Under Review"]]
    })

    return [
        {"value": total, "label": "Animals in Shelter", "indicator": "Blue", "datatype": "Int"},
        {"value": available, "label": "Available for Adoption", "indicator": "Green", "datatype": "Int"},
        {"value": pending, "label": "Pending Applications", "indicator": "Orange", "datatype": "Int"},
    ]
