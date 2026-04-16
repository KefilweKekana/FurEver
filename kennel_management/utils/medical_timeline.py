"""
Animal Medical Timeline — Feature #6
Compile a visual timeline of all medical events for an animal.
"""
import frappe
from frappe.utils import getdate, flt


def get_medical_timeline(animal_name):
    """Build a comprehensive medical timeline for an animal.

    Returns a chronological list of all medical events including vaccinations,
    vet appointments, medications, daily round observations, and status changes.
    """
    events = []

    # 1. Veterinary Appointments
    vet_records = frappe.get_all("Veterinary Appointment", filters={
        "animal": animal_name
    }, fields=["name", "appointment_date", "appointment_type", "status", "veterinarian",
               "diagnosis", "treatment", "notes", "follow_up_date"],
    order_by="appointment_date asc")

    for r in vet_records:
        events.append({
            "date": str(r.appointment_date) if r.appointment_date else "",
            "type": "Veterinary Appointment",
            "icon": "💊",
            "title": f"{r.appointment_type or 'Vet Visit'} — {r.status}",
            "details": {
                "diagnosis": r.diagnosis,
                "treatment": r.treatment,
                "veterinarian": r.veterinarian,
                "notes": r.notes,
                "follow_up": str(r.follow_up_date) if r.follow_up_date else None
            },
            "reference": {"doctype": "Veterinary Appointment", "name": r.name}
        })

    # 2. Veterinary Records
    vet_full = frappe.get_all("Veterinary Record", filters={
        "animal": animal_name
    }, fields=["name", "record_date", "record_type", "diagnosis", "treatment",
               "veterinarian", "notes", "follow_up_required"],
    order_by="record_date asc")

    for r in vet_full:
        events.append({
            "date": str(r.record_date) if r.record_date else "",
            "type": "Veterinary Record",
            "icon": "📋",
            "title": f"{r.record_type or 'Medical Record'}",
            "details": {
                "diagnosis": r.diagnosis,
                "treatment": r.treatment,
                "veterinarian": r.veterinarian,
                "notes": r.notes,
                "follow_up_required": r.follow_up_required
            },
            "reference": {"doctype": "Veterinary Record", "name": r.name}
        })

    # 3. Vaccinations
    vaccinations = frappe.db.sql("""
        SELECT vi.name, vi.parent, vi.vaccination_name, vi.vaccination_date,
               vi.next_due_date, vi.batch_number, vi.administered_by
        FROM `tabVaccination Item` vi
        WHERE vi.parent = %s OR vi.parenttype = 'Animal'
        ORDER BY vi.vaccination_date ASC
    """, animal_name, as_dict=True)

    for v in vaccinations:
        events.append({
            "date": str(v.vaccination_date) if v.vaccination_date else "",
            "type": "Vaccination",
            "icon": "💉",
            "title": f"Vaccination: {v.vaccination_name}",
            "details": {
                "batch_number": v.batch_number,
                "administered_by": v.administered_by,
                "next_due": str(v.next_due_date) if v.next_due_date else None
            },
            "reference": {"doctype": "Vaccination Item", "name": v.name}
        })

    # 4. Medications
    medications = frappe.db.sql("""
        SELECT mi.name, mi.parent, mi.medication_name, mi.start_date, mi.end_date,
               mi.dosage, mi.frequency, mi.status
        FROM `tabMedication Item` mi
        WHERE mi.parent = %s
        ORDER BY mi.start_date ASC
    """, animal_name, as_dict=True)

    for m in medications:
        events.append({
            "date": str(m.start_date) if m.start_date else "",
            "type": "Medication",
            "icon": "💊",
            "title": f"Medication: {m.medication_name} ({m.status or 'Active'})",
            "details": {
                "dosage": m.dosage,
                "frequency": m.frequency,
                "end_date": str(m.end_date) if m.end_date else "Ongoing"
            },
            "reference": {"doctype": "Medication Item", "name": m.name}
        })

    # 5. Behavior Assessments
    assessments = frappe.get_all("Behavior Assessment", filters={
        "animal": animal_name
    }, fields=["name", "assessment_date", "assessor", "temperament_score",
               "aggression_level", "socialization_score", "notes", "recommendation"],
    order_by="assessment_date asc")

    for a in assessments:
        events.append({
            "date": str(a.assessment_date) if a.assessment_date else "",
            "type": "Behavior Assessment",
            "icon": "🧠",
            "title": f"Behavior Assessment (Score: {a.temperament_score or 'N/A'})",
            "details": {
                "assessor": a.assessor,
                "aggression": a.aggression_level,
                "socialization": a.socialization_score,
                "recommendation": a.recommendation,
                "notes": a.notes
            },
            "reference": {"doctype": "Behavior Assessment", "name": a.name}
        })

    # 6. Weight/condition from daily rounds
    daily_rounds = frappe.db.sql("""
        SELECT dr.name, dr.round_date, drd.animal, drd.weight, drd.temperature,
               drd.appetite, drd.notes as detail_notes, drd.needs_attention
        FROM `tabDaily Round` dr
        JOIN `tabDaily Round Detail` drd ON drd.parent = dr.name
        WHERE drd.animal = %s
        ORDER BY dr.round_date ASC
    """, animal_name, as_dict=True)

    for d in daily_rounds:
        if d.needs_attention or d.weight:
            events.append({
                "date": str(d.round_date) if d.round_date else "",
                "type": "Daily Round",
                "icon": "📊",
                "title": f"Daily Round{' ⚠️ Needs Attention' if d.needs_attention else ''}",
                "details": {
                    "weight": d.weight,
                    "temperature": d.temperature,
                    "appetite": d.appetite,
                    "notes": d.detail_notes
                },
                "reference": {"doctype": "Daily Round", "name": d.name}
            })

    # Sort all events chronologically
    events.sort(key=lambda e: e.get("date") or "0000-00-00")

    # Build summary stats
    summary = {
        "total_events": len(events),
        "vet_visits": sum(1 for e in events if "Veterinar" in e["type"]),
        "vaccinations": sum(1 for e in events if e["type"] == "Vaccination"),
        "medications": sum(1 for e in events if e["type"] == "Medication"),
        "assessments": sum(1 for e in events if e["type"] == "Behavior Assessment"),
    }

    return {
        "animal": animal_name,
        "timeline": events,
        "summary": summary
    }
