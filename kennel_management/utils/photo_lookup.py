"""
Photo-Based Animal Lookup — Feature #9
Upload a photo to identify which shelter animal it is, or find similar animals.
Uses vision AI to describe the animal then matches against the database.
"""
import frappe
from frappe.utils import cint, flt


def photo_animal_lookup(image_data, message=""):
    """Use vision AI to identify an animal from a photo and match against shelter database.

    Args:
        image_data: Base64-encoded image data (with or without data URL prefix)
        message: Optional user context ("Is this Rex?" or "Found this dog outside")
    Returns:
        Dict with identified animal details or list of similar shelter animals.
    """
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_ai_chatbot", False):
        return {"success": False, "error": "AI features are not enabled."}

    # Step 1: Use vision AI to describe the animal in the photo
    description = _describe_animal_from_photo(settings, image_data, message)
    if not description:
        return {"success": False, "error": "Could not analyze the image. Please try a clearer photo."}

    # Step 2: Parse description into searchable attributes
    attributes = _parse_animal_description(description)

    # Step 3: Search shelter database for matches
    matches = _find_matching_animals(attributes)

    # Step 4: If user mentioned a name, check direct match
    direct_match = None
    if message:
        import re
        name_hints = re.findall(r'\b[A-Z][a-z]+\b', message)
        for hint in name_hints:
            direct = frappe.db.get_value("Animal",
                {"animal_name": ["like", f"%{hint}%"],
                 "status": ["not in", ["Adopted", "Transferred", "Deceased"]]},
                ["name", "animal_name", "species", "breed", "color", "animal_photo"],
                as_dict=True)
            if direct:
                direct_match = direct
                break

    return {
        "success": True,
        "description": description,
        "parsed_attributes": attributes,
        "direct_match": direct_match,
        "similar_animals": matches[:10],
        "message": _format_lookup_result(description, attributes, direct_match, matches),
    }


def _describe_animal_from_photo(settings, image_data, context=""):
    """Call vision AI to get a structured description of the animal."""
    prompt = (
        "Analyze this animal photo and provide a structured description. "
        "Include: species (dog/cat/bird/rabbit/etc), likely breed or breed mix, "
        "approximate age (puppy/kitten/young/adult/senior), color/coat pattern, "
        "size estimate (small/medium/large), any distinguishing marks, "
        "and overall condition (healthy/injured/thin/etc). "
        "Be specific about colors and patterns. "
        f"{'User context: ' + context if context else ''}"
    )

    # Use the existing vision infrastructure from api.py
    from kennel_management.api import chatbot_vision_query
    try:
        result = chatbot_vision_query(image_data=image_data, message=prompt)
        if result and result.get("reply"):
            return result["reply"]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Photo Lookup Vision Error")

    return None


def _parse_animal_description(description):
    """Parse the AI description into searchable attributes."""
    desc_lower = description.lower()
    attrs = {}

    # Species detection
    species_keywords = {
        "Dog": ["dog", "puppy", "canine", "pup"],
        "Cat": ["cat", "kitten", "feline", "kitty"],
        "Bird": ["bird", "parrot", "budgie", "cockatiel", "avian"],
        "Rabbit": ["rabbit", "bunny", "hare"],
        "Hamster": ["hamster", "gerbil"],
        "Guinea Pig": ["guinea pig"],
        "Reptile": ["reptile", "snake", "lizard", "turtle", "tortoise"],
        "Horse": ["horse", "pony", "equine"],
    }
    for species, keywords in species_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            attrs["species"] = species
            break

    # Color detection
    colors = ["black", "white", "brown", "tan", "golden", "red", "orange", "ginger",
              "grey", "gray", "cream", "brindle", "spotted", "tabby", "calico",
              "tortoiseshell", "merle", "tricolor", "bicolor", "tuxedo", "sable"]
    found_colors = [c for c in colors if c in desc_lower]
    if found_colors:
        attrs["color_hints"] = found_colors

    # Size detection
    for size in ["tiny", "small", "medium", "large", "extra large"]:
        if size in desc_lower:
            attrs["size"] = size.title()
            break

    # Age detection
    age_map = {"puppy": "young", "kitten": "young", "baby": "young", "young": "young",
               "adult": "adult", "mature": "adult", "senior": "senior", "elderly": "senior", "old": "senior"}
    for keyword, age_cat in age_map.items():
        if keyword in desc_lower:
            attrs["age_category"] = age_cat
            break

    attrs["full_description"] = description
    return attrs


def _find_matching_animals(attributes):
    """Search shelter database for animals matching the parsed attributes."""
    filters = {
        "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
    }

    if attributes.get("species"):
        filters["species"] = attributes["species"]

    animals = frappe.get_all("Animal",
        filters=filters,
        fields=["name", "animal_name", "species", "breed", "color", "size",
                "gender", "estimated_age_years", "estimated_age_months",
                "animal_photo", "status", "current_kennel", "temperament"],
        order_by="animal_name",
        limit_page_length=0)

    # Score each animal against the description
    scored = []
    for a in animals:
        score = 0
        reasons = []

        # Color matching
        if attributes.get("color_hints") and a.color:
            animal_color = a.color.lower()
            for c in attributes["color_hints"]:
                if c in animal_color:
                    score += 15
                    reasons.append(f"Color match: {c}")

        # Size matching
        if attributes.get("size") and a.size:
            if attributes["size"].lower() == (a.size or "").lower():
                score += 10
                reasons.append("Size match")

        # Age category matching
        if attributes.get("age_category"):
            years = flt(a.estimated_age_years)
            months = flt(a.estimated_age_months)
            total_months = years * 12 + months
            animal_age_cat = "young" if total_months < 12 else "adult" if total_months < 96 else "senior"
            if animal_age_cat == attributes["age_category"]:
                score += 10
                reasons.append("Age range match")

        if score > 0:
            scored.append({
                "animal_id": a.name,
                "animal_name": a.animal_name,
                "species": a.species,
                "breed": a.breed,
                "color": a.color,
                "size": a.size,
                "status": a.status,
                "photo": a.animal_photo,
                "score": score,
                "reasons": reasons,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _format_lookup_result(description, attributes, direct_match, matches):
    """Format the photo lookup result into a readable message."""
    lines = ["**📸 Photo Analysis Results**\n"]
    lines.append(f"🔍 **AI Description:** {description[:300]}\n")

    if direct_match:
        lines.append(f"✅ **Direct Match Found:** [{direct_match.animal_name}](/app/animal/{direct_match.name})")
        lines.append(f"   Species: {direct_match.species} | Breed: {direct_match.breed or '?'} | Color: {direct_match.color or '?'}\n")

    if matches:
        lines.append(f"🔎 **{len(matches[:10])} Similar Animals in Shelter:**")
        for m in matches[:5]:
            lines.append(
                f"  • **{m['animal_name']}** ({m['species']}/{m['breed'] or '?'}) "
                f"— {m['color'] or '?'}, {m['size'] or '?'} | "
                f"Match: {m['score']}pts ({', '.join(m['reasons'][:3])})"
            )
        if len(matches) > 5:
            lines.append(f"  ... and {len(matches) - 5} more potential matches")
    elif not direct_match:
        lines.append("❌ No matching animals found in the shelter database.")
        lines.append("💡 This animal may be new — consider creating an admission record.")

    return "\n".join(lines)
