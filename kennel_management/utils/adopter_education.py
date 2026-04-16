"""
Adopter Education Portal — Feature #11
Breed-specific care guides, AI-powered Q&A, and post-adoption resources.
"""
import frappe
from frappe.utils import flt


# Default care guides by species
CARE_GUIDES = {
    "Dog": {
        "title": "Dog Care Essentials",
        "sections": [
            {
                "heading": "First 24 Hours",
                "content": "Keep your new dog in a quiet room. Allow them to explore at their own pace. "
                           "Avoid overwhelming them with visitors. Set up a cozy crate or bed."
            },
            {
                "heading": "Feeding",
                "content": "Feed the same food the shelter provided for the first week, then gradually "
                           "transition over 7-10 days. Adult dogs: 2 meals/day. Puppies: 3-4 meals/day."
            },
            {
                "heading": "Exercise",
                "content": "Start with short leash walks (15-20 min). Gradually increase duration. "
                           "Avoid dog parks for the first 2 weeks while your dog adjusts."
            },
            {
                "heading": "Veterinary Care",
                "content": "Schedule a vet visit within the first week. Bring all adoption paperwork "
                           "and vaccination records. Discuss spay/neuter schedule if not yet done."
            },
            {
                "heading": "Common Adjustment Behaviors",
                "content": "Expect: hiding, not eating for 1-2 days, house accidents, mild anxiety. "
                           "These usually resolve within 2-4 weeks (the '3-3-3 Rule')."
            }
        ]
    },
    "Cat": {
        "title": "Cat Care Essentials",
        "sections": [
            {
                "heading": "First 24 Hours",
                "content": "Set up a single 'base camp' room with litter box, food, water, and hiding spots. "
                           "Let your cat explore this room first before opening up the rest of the home."
            },
            {
                "heading": "Feeding",
                "content": "Continue with shelter food for the first week. Provide fresh water daily. "
                           "Adult cats: 2 meals/day. Kittens: 3-4 meals/day. Avoid milk."
            },
            {
                "heading": "Litter Box",
                "content": "One litter box per cat, plus one extra. Scoop daily. Place in quiet, "
                           "accessible locations. Use the same litter type the shelter used initially."
            },
            {
                "heading": "Enrichment",
                "content": "Provide scratching posts, window perches, interactive toys. "
                           "Play sessions 2-3 times daily for 10-15 minutes. Rotate toys weekly."
            },
            {
                "heading": "Common Adjustment Behaviors",
                "content": "Expect: hiding (sometimes for days), not eating for 24-48 hours, "
                           "over-grooming. Most cats fully adjust within 2-4 weeks."
            }
        ]
    }
}


def get_care_guide(species, breed=None):
    """Get a care guide for a specific species/breed."""
    guide = CARE_GUIDES.get(species, CARE_GUIDES.get("Dog"))

    return {
        "species": species,
        "breed": breed,
        "guide": guide,
        "three_three_three_rule": {
            "title": "The 3-3-3 Rule of Adoption",
            "phases": [
                {"period": "First 3 Days", "description": "Feeling overwhelmed. May not eat, drink, or explore. Hiding is normal."},
                {"period": "First 3 Weeks", "description": "Starting to settle in. Learning routines. Personality begins to show."},
                {"period": "First 3 Months", "description": "Fully comfortable. True personality emerges. Bond deepens. Trust established."}
            ]
        }
    }


def get_ai_care_advice(question, species=None, breed=None, animal_name=None):
    """Use AI to answer adopter questions about pet care."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_adopter_education", 0):
        return {"error": "Adopter education feature is not enabled"}

    context = ""
    if animal_name:
        try:
            animal = frappe.get_doc("Animal", animal_name)
            context = f"""
Specific animal context:
Name: {animal.animal_name}
Species: {animal.species}
Breed: {animal.breed or 'Unknown'}
Age: {animal.estimated_age or 'Unknown'}
Temperament: {animal.temperament or 'Unknown'}
Special Notes: {animal.special_notes or 'None'}
Medical Status: {animal.medical_status or 'Unknown'}"""
        except Exception:
            pass

    prompt = f"""You are a veterinary and animal behavior expert helping new pet adopters.

Species: {species or 'Not specified'}
Breed: {breed or 'Not specified'}
{context}

Adopter's Question: {question}

Provide a helpful, accurate, and reassuring answer. Include:
1. Direct answer to the question
2. Practical tips
3. When to contact a veterinarian (if applicable)
4. Common misconceptions to avoid

Keep the tone warm, supportive, and non-judgmental. This person chose to adopt!"""

    from kennel_management.utils.ai_actions import call_llm
    response = call_llm(prompt)
    return {"answer": response, "species": species, "breed": breed}


def get_post_adoption_resources(animal_name):
    """Get personalized post-adoption resource package for an adopted animal."""
    animal = frappe.get_doc("Animal", animal_name)

    resources = {
        "animal": {
            "name": animal.animal_name,
            "species": animal.species,
            "breed": animal.breed,
            "age": animal.estimated_age,
            "medical_status": animal.medical_status,
        },
        "care_guide": get_care_guide(animal.species, animal.breed),
        "emergency_contacts": {
            "shelter_phone": frappe.db.get_single_value("Kennel Management Settings", "shelter_phone") or "",
            "shelter_email": frappe.db.get_single_value("Kennel Management Settings", "shelter_email") or "",
            "after_hours": "For life-threatening emergencies, contact your nearest 24-hour veterinary clinic."
        },
        "upcoming_reminders": [],
        "helpful_links": [
            {"title": "Pet Poison Helpline", "url": "https://www.petpoisonhelpline.com"},
            {"title": "ASPCA Animal Poison Control", "url": "https://www.aspca.org/pet-care/animal-poison-control"},
        ]
    }

    # Add vaccination reminders
    vaccinations = frappe.db.sql("""
        SELECT vaccination_name, next_due_date
        FROM `tabVaccination Item`
        WHERE parent = %s AND next_due_date >= CURDATE()
        ORDER BY next_due_date ASC
    """, animal_name, as_dict=True)

    for v in vaccinations:
        resources["upcoming_reminders"].append({
            "type": "Vaccination",
            "description": f"{v.vaccination_name} due",
            "date": str(v.next_due_date)
        })

    return resources
