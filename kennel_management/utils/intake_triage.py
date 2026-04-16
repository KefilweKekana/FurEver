"""
Smart Intake Triage — Feature #5
AI-powered intake assessment, quarantine recommendations, and urgency scoring.
"""
import frappe
from frappe.utils import today, cint, flt


def perform_intake_triage(animal_data):
    """Evaluate an incoming animal and return triage assessment.

    Args:
        animal_data: dict with species, age, condition_description, source, aggression_signs, etc.

    Returns:
        dict with urgency_score, recommended_actions, quarantine_needed, kennel_recommendation
    """
    urgency_score = 0
    flags = []
    actions = []
    quarantine_needed = False

    species = (animal_data.get("species") or "").lower()
    source = (animal_data.get("source") or "").lower()
    condition = (animal_data.get("condition_description") or "").lower()
    age_years = flt(animal_data.get("estimated_age_years") or 0)
    has_aggression = cint(animal_data.get("aggression_signs") or 0)

    # --- Source-based risk ---
    if "stray" in source or "street" in source:
        urgency_score += 20
        flags.append("Stray animal — unknown vaccination history")
        quarantine_needed = True
        actions.append("Quarantine for minimum 10 days for disease observation")
        actions.append("Immediate rabies vaccination if not visibly vaccinated")
    if "surrender" in source or "owner" in source:
        urgency_score += 5
        actions.append("Collect full medical history from previous owner")
    if "cruelty" in source or "abuse" in source or "neglect" in source:
        urgency_score += 30
        flags.append("⚠️ Cruelty/neglect case — document all injuries")
        actions.append("Photograph all injuries for legal documentation")
        actions.append("Contact SPCA inspector for case file")

    # --- Condition-based risk ---
    injury_words = ["wound", "broken", "bleeding", "fracture", "limp", "injury", "bite"]
    illness_words = ["cough", "sneez", "vomit", "diarr", "discharge", "letharg", "fever"]

    for word in injury_words:
        if word in condition:
            urgency_score += 25
            flags.append("Visible injury detected — needs immediate vet exam")
            actions.append("Priority veterinary examination within 1 hour")
            break

    for word in illness_words:
        if word in condition:
            urgency_score += 20
            quarantine_needed = True
            flags.append("Possible illness symptoms — quarantine recommended")
            actions.append("Isolation from general population immediately")
            actions.append("Full health screening and bloodwork")
            break

    # --- Age-based risk ---
    if age_years < 0.25:
        urgency_score += 15
        flags.append("Very young animal — requires special care")
        actions.append("Bottle feeding protocol if under 4 weeks")
        actions.append("Assign experienced foster if available")
    elif age_years > 10:
        urgency_score += 10
        flags.append("Senior animal — needs comfort-focused housing")
        actions.append("Assign quieter kennel area")

    # --- Behavioral risk ---
    if has_aggression:
        urgency_score += 15
        flags.append("Aggression signs reported — behavior evaluation needed")
        actions.append("House separately from other animals")
        actions.append("Schedule behavior assessment within 48 hours")
        actions.append("Only experienced handlers for this animal")

    # Cap score
    urgency_score = min(urgency_score, 100)

    # Determine priority level
    if urgency_score >= 70:
        priority = "Critical"
    elif urgency_score >= 50:
        priority = "High"
    elif urgency_score >= 25:
        priority = "Medium"
    else:
        priority = "Low"

    # Kennel recommendation
    kennel_rec = _recommend_kennel(species, quarantine_needed, has_aggression, age_years)

    # Standard actions everyone gets
    actions.extend([
        "Microchip scan and registration",
        "Weight and body condition scoring",
        "Flea/tick treatment if needed"
    ])

    return {
        "urgency_score": urgency_score,
        "priority": priority,
        "flags": flags,
        "recommended_actions": actions,
        "quarantine_needed": quarantine_needed,
        "quarantine_days": 10 if quarantine_needed else 0,
        "kennel_recommendation": kennel_rec
    }


def _recommend_kennel(species, quarantine, aggression, age_years):
    """Suggest the best available kennel based on animal profile."""
    filters = {"status": "Active"}

    if quarantine:
        # Look for quarantine/isolation kennels
        kennels = frappe.db.sql("""
            SELECT name, kennel_name, capacity,
                   (SELECT COUNT(*) FROM `tabAnimal` WHERE current_kennel = k.name
                    AND status IN ('Available for Adoption','Under Medical Care','Quarantine','Under Evaluation')) as occupants
            FROM `tabKennel` k
            WHERE status = 'Active'
              AND (kennel_name LIKE '%quarantine%' OR kennel_name LIKE '%isolation%' OR kennel_name LIKE '%medical%')
            HAVING occupants < capacity
            ORDER BY occupants ASC LIMIT 3
        """, as_dict=True)
        if kennels:
            return {"kennel": kennels[0].name, "reason": "Quarantine/isolation kennel with space available"}

    # General placement — find kennel with most space
    kennels = frappe.db.sql("""
        SELECT name, kennel_name, capacity,
               (SELECT COUNT(*) FROM `tabAnimal` WHERE current_kennel = k.name
                AND status IN ('Available for Adoption','Under Medical Care','Quarantine','Under Evaluation','Boarding')) as occupants
        FROM `tabKennel` k
        WHERE status = 'Active'
        HAVING occupants < capacity
        ORDER BY (capacity - occupants) DESC LIMIT 3
    """, as_dict=True)

    if kennels:
        return {"kennel": kennels[0].name, "reason": f"Most available space ({kennels[0].capacity - kennels[0].occupants} spots)"}

    return {"kennel": None, "reason": "⚠️ No kennels with available space — consider emergency fostering"}


def ai_triage_assessment(animal_name):
    """Use AI to provide a detailed triage assessment for an animal.

    Args:
        animal_name: Name (ID) of the Animal doctype record
    """
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_intake_triage", 0):
        return {"error": "Intake triage feature is not enabled"}

    animal = frappe.get_doc("Animal", animal_name)

    prompt = f"""You are a veterinary triage specialist. Assess this incoming shelter animal:

Species: {animal.species}
Breed: {animal.breed or 'Unknown'}
Age: {animal.estimated_age or 'Unknown'}
Sex: {animal.sex or 'Unknown'}
Color: {animal.color or 'Unknown'}
Weight: {animal.weight or 'Unknown'}
Source: {animal.source_type or 'Unknown'}
Medical Status: {animal.medical_status or 'Unknown'}
Notes: {animal.special_notes or 'None'}

Provide:
1. Initial health risk assessment (1-10)
2. Recommended immediate actions (top 5)
3. Quarantine recommendation (yes/no + reason)
4. Special housing needs
5. Estimated time to adoption-ready status"""

    from kennel_management.utils.ai_actions import call_llm
    response = call_llm(prompt)
    return {"assessment": response, "animal": animal_name}
