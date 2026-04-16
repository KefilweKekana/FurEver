"""
AI Matching Engine — Adoption matching + Lost & Found matching.

Computes compatibility scores between animals and adoption applicants,
and cross-references lost reports with shelter animals.
"""
import frappe
from frappe.utils import today, getdate, add_days, cint, flt
import json


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ADOPTION MATCHING ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_adoption_matches(animal=None, applicant=None, top_n=5):
    """Compute adoption compatibility scores between animals and applicants.

    Returns top matches with detailed scoring breakdown.
    """
    # Get available animals
    animal_filters = {
        "status": "Available for Adoption",
    }
    if animal:
        resolved = _resolve_animal_id(animal)
        if resolved:
            animal_filters = {"name": resolved}

    animals = frappe.get_all("Animal", filters=animal_filters, fields=[
        "name", "animal_name", "species", "breed", "gender", "size", "energy_level",
        "temperament", "good_with_dogs", "good_with_cats", "good_with_children",
        "is_special_needs", "estimated_age_years", "estimated_age_months",
        "intake_date", "spay_neuter_status", "weight_kg",
    ], limit_page_length=0)

    if not animals:
        return {"success": True, "matches": [], "message": "No available animals found for matching."}

    # Get behavior assessments for these animals
    behavior_map = {}
    for a in animals:
        ba = frappe.get_all("Behavior Assessment", filters={"animal": a.name},
            fields=["aggression_score", "fear_score", "sociability_score", "trainability_score",
                    "energy_level", "overall_temperament", "dog_sociability", "cat_sociability",
                    "child_reaction", "resource_guarding", "handling_tolerance"],
            order_by="assessment_date desc", limit=1)
        if ba:
            behavior_map[a.name] = ba[0]

    # Get pending applicants
    app_filters = {"status": ["in", ["Pending", "Under Review", "Home Check Scheduled",
                                      "Home Check Completed", "Approved"]]}
    if applicant:
        resolved_app = _resolve_applicant_id(applicant)
        if resolved_app:
            app_filters = {"name": resolved_app}

    applicants = frappe.get_all("Adoption Application", filters=app_filters, fields=[
        "name", "applicant_name", "animal", "animal_name", "species_preference",
        "housing_type", "own_or_rent", "has_yard", "yard_fenced",
        "number_of_adults", "number_of_children", "number_of_current_pets",
        "previous_pet_experience", "status",
    ], limit_page_length=0)

    if not applicants:
        return {"success": True, "matches": [], "message": "No pending applications found for matching."}

    # Compute all match scores
    all_matches = []
    for app in applicants:
        for anim in animals:
            # Skip if applicant has a specific animal preference that doesn't match
            if app.animal and app.animal != anim.name:
                continue
            if app.species_preference and app.species_preference != anim.species:
                continue

            score, breakdown = _compute_compatibility_score(app, anim, behavior_map.get(anim.name))
            all_matches.append({
                "applicant_id": app.name,
                "applicant_name": app.applicant_name,
                "applicant_status": app.status,
                "animal_id": anim.name,
                "animal_name": anim.animal_name,
                "species": anim.species,
                "breed": anim.breed,
                "score": round(score, 1),
                "grade": _score_to_grade(score),
                "breakdown": breakdown,
            })

    # Sort by score descending
    all_matches.sort(key=lambda x: x["score"], reverse=True)
    top_matches = all_matches[:top_n]

    # Format results
    match_lines = []
    for m in top_matches:
        reasons = [f"{k}: {v['score']}/{v['max']} — {v['reason']}" for k, v in m["breakdown"].items() if v.get("reason")]
        match_lines.append(
            f"**{m['animal_name']}** ({m['species']}/{m['breed'] or '?'}) ↔ **{m['applicant_name']}** — "
            f"Score: **{m['score']}%** ({m['grade']})"
        )

    return {
        "success": True,
        "matches": top_matches,
        "message": f"Found {len(all_matches)} potential matches. Top {len(top_matches)}:\n\n" +
            "\n".join(match_lines) if match_lines else "No compatible matches found.",
        "total_evaluated": len(all_matches),
    }


def _compute_compatibility_score(applicant, animal, behavior=None):
    """Compute a 0-100 compatibility score between an applicant and animal."""
    breakdown = {}
    total_score = 0
    total_max = 0

    # 1. Living space (20 points)
    space_score = 10  # baseline
    space_reason = ""
    if animal.size in ("Large", "Giant"):
        if applicant.has_yard:
            space_score = 20
            space_reason = "Large animal + has yard = great"
        elif applicant.housing_type == "House":
            space_score = 14
            space_reason = "Large animal + house but no yard"
        else:
            space_score = 6
            space_reason = "Large animal in apartment — not ideal"
    elif animal.size in ("Medium",):
        if applicant.has_yard or applicant.housing_type in ("House", "Townhouse"):
            space_score = 18
            space_reason = "Medium animal with adequate space"
        else:
            space_score = 12
            space_reason = "Medium animal in apartment — manageable"
    elif animal.size in ("Tiny", "Small"):
        space_score = 17  # small animals adapt well
        space_reason = "Small animal — flexible on space"
        if applicant.has_yard:
            space_score = 20
            space_reason = "Small animal + yard = great"
    breakdown["Living Space"] = {"score": space_score, "max": 20, "reason": space_reason}
    total_score += space_score
    total_max += 20

    # 2. Energy level match (15 points)
    energy_score = 8
    energy_reason = ""
    animal_energy = (behavior.energy_level if behavior and behavior.energy_level else animal.energy_level) or "Medium"
    has_yard = applicant.has_yard
    if animal_energy in ("High", "Very High"):
        if has_yard and applicant.yard_fenced:
            energy_score = 15
            energy_reason = "High energy + fenced yard = perfect"
        elif has_yard:
            energy_score = 12
            energy_reason = "High energy + yard (not fenced)"
        else:
            energy_score = 5
            energy_reason = "High energy without yard — challenging"
    elif animal_energy == "Medium":
        energy_score = 12
        energy_reason = "Medium energy — adaptable"
        if has_yard:
            energy_score = 14
    elif animal_energy in ("Low", "Very Low"):
        energy_score = 13
        energy_reason = "Low energy — suits most homes"
    breakdown["Energy Match"] = {"score": energy_score, "max": 15, "reason": energy_reason}
    total_score += energy_score
    total_max += 15

    # 3. Child compatibility (15 points)
    child_score = 10
    child_reason = ""
    num_kids = cint(applicant.number_of_children)
    animal_kids = animal.good_with_children or "Unknown"
    if behavior and behavior.child_reaction:
        animal_kids_behavior = behavior.child_reaction
    else:
        animal_kids_behavior = None

    if num_kids > 0:
        if animal_kids == "Yes" or (animal_kids_behavior and "friendly" in (animal_kids_behavior or "").lower()):
            child_score = 15
            child_reason = "Good with children + family has kids = great match"
        elif animal_kids == "No" or (animal_kids_behavior and ("aggressive" in (animal_kids_behavior or "").lower() or "fearful" in (animal_kids_behavior or "").lower())):
            child_score = 2
            child_reason = "NOT good with children — family has kids — poor match"
        else:
            child_score = 8
            child_reason = "Unknown child compatibility — family has kids — needs assessment"
    else:
        child_score = 13
        child_reason = "No children — compatibility not a concern"
    breakdown["Child Safety"] = {"score": child_score, "max": 15, "reason": child_reason}
    total_score += child_score
    total_max += 15

    # 4. Pet compatibility (10 points)
    pet_score = 7
    pet_reason = ""
    current_pets = cint(applicant.number_of_current_pets)
    if current_pets > 0:
        dog_ok = animal.good_with_dogs or "Unknown"
        cat_ok = animal.good_with_cats or "Unknown"
        if dog_ok == "Yes" and cat_ok == "Yes":
            pet_score = 10
            pet_reason = "Good with other animals + applicant has pets"
        elif dog_ok == "No" or cat_ok == "No":
            pet_score = 3
            pet_reason = "Not good with other animals — applicant has pets"
        else:
            pet_score = 6
            pet_reason = "Unknown pet compatibility — needs supervised introduction"
    else:
        pet_score = 9
        pet_reason = "No existing pets — no conflict"
    breakdown["Pet Compatibility"] = {"score": pet_score, "max": 10, "reason": pet_reason}
    total_score += pet_score
    total_max += 10

    # 5. Experience level (15 points)
    exp_score = 8
    exp_reason = ""
    experience = (applicant.previous_pet_experience or "").lower()
    is_difficult = (animal.temperament or "").lower() in ("aggressive", "fearful", "anxious")
    if behavior:
        aggr = cint(behavior.aggression_score)
        fear = cint(behavior.fear_score)
        if aggr >= 4 or fear >= 4:
            is_difficult = True

    if is_difficult:
        if "extensive" in experience or "professional" in experience or "years" in experience:
            exp_score = 15
            exp_reason = "Difficult temperament + experienced owner = good match"
        elif "some" in experience or "previous" in experience:
            exp_score = 8
            exp_reason = "Difficult temperament + moderate experience — may work with support"
        else:
            exp_score = 3
            exp_reason = "Difficult temperament + inexperienced — not recommended"
    else:
        if "extensive" in experience or "years" in experience:
            exp_score = 15
            exp_reason = "Easy temperament + experienced owner = excellent"
        elif "none" in experience or "first" in experience or not experience:
            exp_score = 10
            exp_reason = "Easy temperament — suitable for first-time owner"
        else:
            exp_score = 12
            exp_reason = "Good temperament + adequate experience"
    breakdown["Experience"] = {"score": exp_score, "max": 15, "reason": exp_reason}
    total_score += exp_score
    total_max += 15

    # 6. Housing stability (10 points)
    housing_score = 7
    housing_reason = ""
    if applicant.own_or_rent == "Own":
        housing_score = 10
        housing_reason = "Homeowner — stable housing"
    elif applicant.own_or_rent == "Rent":
        housing_score = 6
        housing_reason = "Renting — verify pet policy"
    else:
        housing_score = 5
        housing_reason = "Housing status unknown"
    breakdown["Housing Stability"] = {"score": housing_score, "max": 10, "reason": housing_reason}
    total_score += housing_score
    total_max += 10

    # 7. Behavioral fit (15 points)
    behav_score = 8
    behav_reason = ""
    if behavior:
        sociability = cint(behavior.sociability_score) or 3
        trainability = cint(behavior.trainability_score) or 3
        aggression = cint(behavior.aggression_score) or 1

        if sociability >= 4 and aggression <= 2 and trainability >= 3:
            behav_score = 15
            behav_reason = "Excellent behavior profile — social, trainable, low aggression"
        elif sociability >= 3 and aggression <= 3:
            behav_score = 11
            behav_reason = "Good behavior — moderately social"
        elif aggression >= 4:
            behav_score = 4
            behav_reason = "High aggression score — needs experienced handler"
        else:
            behav_score = 8
            behav_reason = "Average behavior profile"
    else:
        behav_reason = "No behavior assessment on file"
    breakdown["Behavioral Fit"] = {"score": behav_score, "max": 15, "reason": behav_reason}
    total_score += behav_score
    total_max += 15

    # Calculate percentage
    percentage = (total_score / total_max * 100) if total_max > 0 else 0
    return percentage, breakdown


def _score_to_grade(score):
    if score >= 85:
        return "Excellent Match"
    elif score >= 70:
        return "Good Match"
    elif score >= 55:
        return "Fair Match"
    elif score >= 40:
        return "Below Average"
    else:
        return "Poor Match"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOST & FOUND MATCHING ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_lost_found_matches(report=None, animal=None):
    """Cross-reference lost reports with shelter animals.

    When a lost report comes in → check all shelter animals.
    When a stray is admitted → check all open lost reports.
    """
    matches = []

    if animal:
        # Match a specific animal against all open lost reports
        animal_id = _resolve_animal_id(animal)
        if not animal_id:
            return {"success": False, "error": f"Could not find animal: {animal}"}

        animal_doc = frappe.get_doc("Animal", animal_id)
        lost_reports = frappe.get_all("Lost and Found Report",
            filters={"status": ["in", ["Open", "Investigating"]], "report_type": "Lost"},
            fields=["name", "species", "breed", "color", "gender", "last_seen_location",
                    "last_seen_date", "description", "reporter_name", "microchip_number"],
            limit_page_length=0)

        for lr in lost_reports:
            score, reasons = _compute_lost_match_score(animal_doc, lr)
            if score >= 30:
                matches.append({
                    "report_id": lr.name,
                    "report_type": "Lost",
                    "reporter_name": lr.reporter_name,
                    "animal_id": animal_doc.name,
                    "animal_name": animal_doc.animal_name,
                    "score": round(score, 1),
                    "reasons": reasons,
                })

    elif report:
        # Match a specific report against all shelter animals
        report_doc = frappe.get_doc("Lost and Found Report", report)
        animals = frappe.get_all("Animal",
            filters={"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]},
            fields=["name", "animal_name", "species", "breed", "color", "gender",
                    "microchip_number", "intake_date", "source"],
            limit_page_length=0)

        for anim in animals:
            score, reasons = _compute_lost_match_score(anim, report_doc)
            if score >= 30:
                matches.append({
                    "report_id": report_doc.name,
                    "report_type": report_doc.report_type,
                    "reporter_name": report_doc.reporter_name,
                    "animal_id": anim.name,
                    "animal_name": anim.animal_name,
                    "score": round(score, 1),
                    "reasons": reasons,
                })

    else:
        # Match ALL open lost reports against ALL shelter animals
        lost_reports = frappe.get_all("Lost and Found Report",
            filters={"status": ["in", ["Open", "Investigating"]], "report_type": "Lost",
                     "matched_animal": ["is", "not set"]},
            fields=["name", "species", "breed", "color", "gender", "last_seen_location",
                    "last_seen_date", "description", "reporter_name", "microchip_number"],
            limit_page_length=0)

        animals = frappe.get_all("Animal",
            filters={"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]],
                     "source": ["in", ["Stray", "Rescue", "Confiscation", ""]]},
            fields=["name", "animal_name", "species", "breed", "color", "gender",
                    "microchip_number", "intake_date", "source"],
            limit_page_length=0)

        for lr in lost_reports:
            for anim in animals:
                score, reasons = _compute_lost_match_score(anim, lr)
                if score >= 40:
                    matches.append({
                        "report_id": lr.name,
                        "report_type": "Lost",
                        "reporter_name": lr.reporter_name,
                        "animal_id": anim.name,
                        "animal_name": anim.animal_name,
                        "score": round(score, 1),
                        "reasons": reasons,
                    })

    matches.sort(key=lambda x: x["score"], reverse=True)
    top_matches = matches[:10]

    # Format message
    if top_matches:
        lines = []
        for m in top_matches:
            reason_str = ", ".join(m["reasons"][:3])
            lines.append(f"**{m['animal_name']}** ↔ Report {m['report_id']} ({m['reporter_name']}) — **{m['score']}%** match ({reason_str})")
        msg = f"Found {len(matches)} potential matches:\n\n" + "\n".join(lines)
    else:
        msg = "No matching animals found for the open lost reports."

    return {
        "success": True,
        "matches": top_matches,
        "message": msg,
        "total_matches": len(matches),
    }


def _compute_lost_match_score(animal, report):
    """Compute match score between an animal and a lost/found report."""
    score = 0
    reasons = []

    # Microchip match = definitive (100%)
    animal_chip = getattr(animal, "microchip_number", None) or ""
    report_chip = getattr(report, "microchip_number", None) or ""
    if animal_chip and report_chip and animal_chip.strip().lower() == report_chip.strip().lower():
        return 100, ["Microchip number matches!"]

    # Species match (mandatory filter — skip if no match)
    animal_species = (getattr(animal, "species", "") or "").lower()
    report_species = (getattr(report, "species", "") or "").lower()
    if animal_species and report_species:
        if animal_species == report_species:
            score += 25
            reasons.append("Same species")
        else:
            return 0, []  # Different species = no match

    # Breed match
    animal_breed = (getattr(animal, "breed", "") or "").lower()
    report_breed = (getattr(report, "breed", "") or "").lower()
    if animal_breed and report_breed:
        if animal_breed == report_breed:
            score += 25
            reasons.append("Exact breed match")
        elif _fuzzy_match(animal_breed, report_breed):
            score += 15
            reasons.append("Similar breed")

    # Color match
    animal_color = (getattr(animal, "color", "") or "").lower()
    report_color = (getattr(report, "color", "") or "").lower()
    if animal_color and report_color:
        if animal_color == report_color:
            score += 20
            reasons.append("Exact color match")
        elif _fuzzy_match(animal_color, report_color):
            score += 10
            reasons.append("Similar coloring")

    # Gender match
    animal_gender = (getattr(animal, "gender", "") or "").lower()
    report_gender = (getattr(report, "gender", "") or "").lower()
    if animal_gender and report_gender and animal_gender != "unknown" and report_gender != "unknown":
        if animal_gender == report_gender:
            score += 10
            reasons.append("Same gender")
        else:
            score -= 10

    # Date proximity (animal intake vs. last seen date)
    intake_date = getattr(animal, "intake_date", None)
    last_seen = getattr(report, "last_seen_date", None)
    if intake_date and last_seen:
        try:
            days_diff = abs((getdate(intake_date) - getdate(last_seen)).days)
            if days_diff <= 3:
                score += 15
                reasons.append(f"Found within {days_diff} days of being lost")
            elif days_diff <= 7:
                score += 10
                reasons.append(f"Found within a week of being lost")
            elif days_diff <= 14:
                score += 5
                reasons.append("Found within 2 weeks")
        except Exception:
            pass

    # Description keywords match
    description = (getattr(report, "description", "") or "").lower()
    if description:
        animal_name = (getattr(animal, "animal_name", "") or "").lower()
        if animal_breed and animal_breed in description:
            score += 5
            reasons.append("Breed mentioned in description")
        if animal_color and animal_color in description:
            score += 5

    return max(score, 0), reasons


def _fuzzy_match(str1, str2):
    """Simple fuzzy matching — check if strings share significant words."""
    if not str1 or not str2:
        return False
    words1 = set(str1.lower().split())
    words2 = set(str2.lower().split())
    # Remove common filler words
    fillers = {"and", "the", "with", "mix", "mixed", "cross", "type", "like", "a", "an"}
    words1 -= fillers
    words2 -= fillers
    if not words1 or not words2:
        return False
    overlap = words1 & words2
    return len(overlap) >= 1


def _resolve_animal_id(identifier):
    """Resolve animal identifier to docname."""
    if not identifier:
        return None
    if frappe.db.exists("Animal", identifier):
        return identifier
    matches = frappe.get_all("Animal", filters={"animal_name": ["like", f"%{identifier}%"]},
        fields=["name"], order_by="creation desc", limit=1)
    return matches[0].name if matches else None


def _resolve_applicant_id(identifier):
    """Resolve applicant identifier to docname."""
    if not identifier:
        return None
    if frappe.db.exists("Adoption Application", identifier):
        return identifier
    matches = frappe.get_all("Adoption Application",
        filters={"applicant_name": ["like", f"%{identifier}%"]},
        fields=["name"], order_by="creation desc", limit=1)
    return matches[0].name if matches else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCHEDULED: AUTO-MATCH ON ADMISSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def auto_match_on_admission(doc, method=None):
    """Called when a new animal is admitted — auto-check against lost reports.

    Note: `doc` is an Animal Admission document. We use `doc.animal` to get
    the linked Animal record ID for matching.
    """
    try:
        animal_id = getattr(doc, "animal", None)
        if not animal_id:
            return

        animal_doc = frappe.get_doc("Animal", animal_id)
        if animal_doc.species:
            result = compute_lost_found_matches(animal=animal_id)
            if result.get("matches"):
                top = result["matches"][0]
                if top["score"] >= 60:
                    # High confidence match — create alert
                    frappe.get_doc({
                        "doctype": "ToDo",
                        "description": (
                            f"🔍 Potential lost pet match! {animal_doc.animal_name} ({animal_doc.species}/{animal_doc.breed or '?'}) "
                            f"may match lost report {top['report_id']} from {top['reporter_name']} "
                            f"— {top['score']}% confidence. Reasons: {', '.join(top['reasons'][:3])}"
                        ),
                        "reference_type": "Animal",
                        "reference_name": animal_id,
                        "priority": "Urgent" if top["score"] >= 80 else "High",
                    }).insert(ignore_permissions=True)

                    # Update the lost report status
                    frappe.db.set_value("Lost and Found Report", top["report_id"],
                                       "status", "Investigating")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Auto Lost-Found Match Error")
