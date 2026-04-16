"""
Length-of-Stay Alerts + Predictive Adoption Scoring — Features #3 & #11
Auto-flag long-stay animals, generate promotion suggestions,
and predict adoption likelihood using historical data.
"""
import frappe
from frappe.utils import today, add_days, getdate, cint, flt, date_diff


def check_length_of_stay_alerts():
    """Daily task: flag animals with extended stays and generate actionable suggestions."""
    now = today()
    thresholds = [
        (90, "Critical", "🔴"),
        (60, "Urgent", "🟠"),
        (30, "High", "🟡"),
    ]

    for days, priority, icon in thresholds:
        cutoff = add_days(now, -days)
        animals = frappe.db.sql("""
            SELECT name, animal_name, species, breed, intake_date, status,
                   DATEDIFF(%s, intake_date) as days_in_shelter
            FROM `tabAnimal`
            WHERE status = 'Available for Adoption'
              AND intake_date <= %s
              AND intake_date > %s
            ORDER BY intake_date ASC
        """, (now, cutoff, add_days(cutoff, -30)), as_dict=True)

        for animal in animals:
            # Check if we already flagged this animal at this tier recently
            existing = frappe.db.exists("ToDo", {
                "reference_type": "Animal",
                "reference_name": animal.name,
                "description": ["like", f"%{days}+ days in shelter%"],
                "status": "Open",
            })
            if existing:
                continue

            suggestions = _get_promotion_suggestions(animal, days)
            frappe.get_doc({
                "doctype": "ToDo",
                "description": (
                    f"{icon} **{animal.animal_name}** ({animal.species}/{animal.breed or '?'}) — "
                    f"{animal.days_in_shelter} days in shelter ({days}+ days threshold)\n\n"
                    f"**Suggested actions:**\n{suggestions}"
                ),
                "reference_type": "Animal",
                "reference_name": animal.name,
                "priority": priority,
                "allocated_to": _get_kennel_manager(),
            }).insert(ignore_permissions=True)

    frappe.db.commit()


def _get_promotion_suggestions(animal, days):
    """Generate actionable suggestions based on stay length and animal profile."""
    suggestions = []

    if days >= 90:
        suggestions.append("• Feature in 'Long-Stay Spotlight' social media campaign")
        suggestions.append("• Consider reduced adoption fee or fee waiver")
        suggestions.append("• Arrange professional photo/video shoot")
        suggestions.append("• Contact breed-specific rescue organizations")
        suggestions.append("• Evaluate for foster-to-adopt program")
    elif days >= 60:
        suggestions.append("• Add to 'Featured Pets' on website and social media")
        suggestions.append("• Create detailed personality profile video")
        suggestions.append("• Reach out to previous adopters for referrals")
        suggestions.append("• Consider temporary foster for socialization")
    else:
        suggestions.append("• Ensure high-quality photos are on file")
        suggestions.append("• Update online listing with personality details")
        suggestions.append("• Include in next adoption event")

    if animal.species == "Dog":
        suggestions.append("• Schedule behavior assessment update if not recent")
    elif animal.species == "Cat":
        suggestions.append("• Ensure cat cafe or free-roam visibility if temperament allows")

    return "\n".join(suggestions)


def _get_kennel_manager():
    """Get first active Kennel Manager user."""
    managers = frappe.get_all("Has Role",
        filters={"role": "Kennel Manager", "parenttype": "User"},
        fields=["parent"], limit=1)
    if managers:
        return managers[0].parent
    return None


# ──────────────────────────────────────────────────────────────
# Predictive Adoption Scoring — Feature #11
# ──────────────────────────────────────────────────────────────

def compute_adoption_score(animal_id):
    """Predict adoption likelihood (0-100) and estimated days to adoption.

    Scoring factors based on historical adoption data:
    - Species/breed popularity
    - Age preference
    - Size preference
    - Temperament
    - Medical status
    - Photo quality
    - Special needs impact
    - Current length of stay
    """
    animal = frappe.get_doc("Animal", animal_id)

    score = 50  # Base score
    factors = []

    # 1. Species popularity (from historical adoptions)
    species_score = _score_species_popularity(animal.species)
    score += species_score
    factors.append({"factor": "Species demand", "impact": species_score,
                    "detail": f"{animal.species} — {'high' if species_score > 5 else 'moderate' if species_score > 0 else 'lower'} demand"})

    # 2. Breed desirability
    breed_score = _score_breed(animal.species, animal.breed)
    score += breed_score
    factors.append({"factor": "Breed appeal", "impact": breed_score,
                    "detail": f"{animal.breed or 'Mixed/Unknown'}"})

    # 3. Age factor — younger typically adopt faster
    age_score = _score_age(animal)
    score += age_score
    factors.append({"factor": "Age", "impact": age_score,
                    "detail": _format_age(animal)})

    # 4. Size preference
    size_score = _score_size(animal.size)
    score += size_score
    factors.append({"factor": "Size", "impact": size_score,
                    "detail": animal.size or "Unknown"})

    # 5. Temperament
    temp_score = _score_temperament(animal.temperament)
    score += temp_score
    factors.append({"factor": "Temperament", "impact": temp_score,
                    "detail": animal.temperament or "Not assessed"})

    # 6. Good with (kids/dogs/cats)
    compat_score = _score_compatibility(animal)
    score += compat_score
    factors.append({"factor": "Compatibility", "impact": compat_score,
                    "detail": _format_compatibility(animal)})

    # 7. Medical/special needs
    medical_score = _score_medical(animal)
    score += medical_score
    factors.append({"factor": "Health status", "impact": medical_score,
                    "detail": f"Spay/neuter: {animal.spay_neuter_status or 'Unknown'}" +
                              (" | Special needs" if animal.is_special_needs else "")})

    # 8. Photo availability
    photo_score = 5 if animal.animal_photo else -5
    score += photo_score
    factors.append({"factor": "Photo on file", "impact": photo_score,
                    "detail": "Yes" if animal.animal_photo else "No photo — add one!"})

    # 9. Training status
    train_score = _score_training(animal)
    score += train_score
    factors.append({"factor": "Training", "impact": train_score,
                    "detail": _format_training(animal)})

    # 10. Length of stay penalty
    if animal.intake_date:
        los = date_diff(today(), animal.intake_date)
        if los > 90:
            los_score = -10
        elif los > 60:
            los_score = -5
        elif los > 30:
            los_score = -2
        elif los < 7:
            los_score = 5  # "New arrival" boost
        else:
            los_score = 0
        score += los_score
        factors.append({"factor": "Length of stay", "impact": los_score,
                        "detail": f"{los} days"})

    # Clamp score
    score = max(5, min(100, score))

    # Estimate days to adoption based on score + historical average
    avg_days = _get_historical_avg_days(animal.species, animal.breed)
    score_factor = (100 - score) / 50  # Higher score = fewer days
    estimated_days = max(1, round(avg_days * score_factor))

    # Generate recommendations
    recommendations = _generate_adoption_recommendations(animal, factors, score)

    return {
        "success": True,
        "animal_id": animal_id,
        "animal_name": animal.animal_name,
        "adoption_score": score,
        "estimated_days_to_adoption": estimated_days,
        "rating": "Excellent" if score >= 80 else "Good" if score >= 60 else "Moderate" if score >= 40 else "Challenging",
        "factors": factors,
        "recommendations": recommendations,
        "message": (
            f"**{animal.animal_name}** — Adoption Score: **{score}/100** "
            f"({'⭐' * (score // 20)})\n\n"
            f"Rating: **{'Excellent' if score >= 80 else 'Good' if score >= 60 else 'Moderate' if score >= 40 else 'Challenging'}** | "
            f"Est. adoption: ~{estimated_days} days\n\n"
            + "\n".join([f"• {f['factor']}: {'+' if f['impact'] >= 0 else ''}{f['impact']} — {f['detail']}" for f in factors])
            + "\n\n**Recommendations:**\n" + "\n".join([f"• {r}" for r in recommendations])
        ),
    }


def compute_all_adoption_scores():
    """Batch-compute adoption scores for all available animals. Returns ranked list."""
    animals = frappe.get_all("Animal",
        filters={"status": "Available for Adoption"},
        fields=["name", "animal_name"],
        order_by="animal_name", limit_page_length=0)

    results = []
    for a in animals:
        try:
            result = compute_adoption_score(a.name)
            results.append({
                "animal_id": a.name,
                "animal_name": a.animal_name,
                "score": result["adoption_score"],
                "rating": result["rating"],
                "estimated_days": result["estimated_days_to_adoption"],
            })
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Adoption Score Error: {a.name}")

    results.sort(key=lambda x: x["score"])  # Lowest first = needs most help
    return {
        "success": True,
        "animals": results,
        "total": len(results),
        "message": _format_batch_scores(results),
    }


def _format_batch_scores(results):
    """Format batch scores into a readable message."""
    if not results:
        return "No animals currently available for adoption."

    lines = ["**Adoption Likelihood Rankings** (lowest score = needs most promotion)\n"]

    # Bottom 5 — need help
    needing_help = results[:5]
    if needing_help:
        lines.append("🔴 **Needs Promotion:**")
        for r in needing_help:
            lines.append(f"  • {r['animal_name']} — Score: {r['score']}/100 ({r['rating']}, ~{r['estimated_days']} days)")

    # Top 5 — likely to be adopted soon
    likely = sorted(results, key=lambda x: x["score"], reverse=True)[:5]
    if likely:
        lines.append("\n🟢 **Likely Quick Adoption:**")
        for r in likely:
            lines.append(f"  • {r['animal_name']} — Score: {r['score']}/100 ({r['rating']}, ~{r['estimated_days']} days)")

    avg_score = round(sum(r["score"] for r in results) / len(results))
    lines.append(f"\n📊 **Average score:** {avg_score}/100 across {len(results)} animals")

    return "\n".join(lines)


# ── Scoring Helper Functions ──

def _score_species_popularity(species):
    """Score based on historical adoption rates by species."""
    adopted = frappe.db.sql("""
        SELECT species, COUNT(*) as cnt FROM `tabAnimal`
        WHERE status = 'Adopted' AND species IS NOT NULL
        GROUP BY species
    """, as_dict=True)
    total = sum(a.cnt for a in adopted) or 1
    species_map = {a.species: a.cnt / total for a in adopted}
    rate = species_map.get(species, 0)
    if rate > 0.4:
        return 10
    elif rate > 0.2:
        return 5
    elif rate > 0.1:
        return 0
    return -5


def _score_breed(species, breed):
    if not breed or breed.lower() in ("mixed", "unknown", "mixed breed"):
        return -2  # Mixed breeds adopt slightly slower
    # Check if this breed has been adopted before
    count = frappe.db.count("Animal", {"breed": breed, "status": "Adopted"})
    if count >= 5:
        return 8
    elif count >= 2:
        return 4
    return 0


def _score_age(animal):
    years = flt(animal.estimated_age_years)
    months = flt(animal.estimated_age_months)
    total_months = years * 12 + months
    if total_months == 0:
        return 0  # Unknown age
    if total_months <= 12:
        return 10  # Puppies/kittens
    elif total_months <= 36:
        return 5  # Young adults
    elif total_months <= 84:
        return 0  # Adults
    elif total_months <= 120:
        return -5  # Senior
    return -8  # Very senior


def _format_age(animal):
    years = flt(animal.estimated_age_years)
    months = flt(animal.estimated_age_months)
    if years:
        return f"{int(years)}y {int(months)}m" if months else f"{int(years)}y"
    elif months:
        return f"{int(months)}m"
    return "Unknown"


def _score_size(size):
    size_scores = {
        "Small": 5,
        "Medium": 3,
        "Large": 0,
        "Extra Large": -3,
        "Tiny": 5,
    }
    return size_scores.get(size, 0)


def _score_temperament(temperament):
    positive = {"Friendly": 10, "Playful": 8, "Calm": 6, "Gentle": 7, "Affectionate": 8}
    neutral = {"Independent": 0, "Curious": 3}
    negative = {"Shy": -3, "Anxious": -5, "Aggressive": -15, "Fearful": -5}
    return positive.get(temperament, neutral.get(temperament, negative.get(temperament, 0)))


def _score_compatibility(animal):
    score = 0
    if getattr(animal, "good_with_children", "") == "Yes":
        score += 5
    elif getattr(animal, "good_with_children", "") == "No":
        score -= 3
    if getattr(animal, "good_with_dogs", "") == "Yes":
        score += 3
    if getattr(animal, "good_with_cats", "") == "Yes":
        score += 3
    return score


def _format_compatibility(animal):
    parts = []
    for field, label in [("good_with_children", "Kids"), ("good_with_dogs", "Dogs"), ("good_with_cats", "Cats")]:
        val = getattr(animal, field, "Unknown")
        if val and val != "Unknown":
            parts.append(f"{label}: {val}")
    return ", ".join(parts) if parts else "Not assessed"


def _score_medical(animal):
    score = 0
    if animal.spay_neuter_status in ("Spayed", "Neutered"):
        score += 5  # Already fixed = easier adoption
    if animal.is_special_needs:
        score -= 10
    return score


def _score_training(animal):
    score = 0
    if getattr(animal, "house_trained", "") == "Yes":
        score += 4
    if getattr(animal, "leash_trained", "") == "Yes":
        score += 3
    if getattr(animal, "crate_trained", "") == "Yes":
        score += 2
    return score


def _format_training(animal):
    trained = []
    if getattr(animal, "house_trained", "") == "Yes":
        trained.append("House")
    if getattr(animal, "leash_trained", "") == "Yes":
        trained.append("Leash")
    if getattr(animal, "crate_trained", "") == "Yes":
        trained.append("Crate")
    return ", ".join(trained) + " trained" if trained else "Not trained/assessed"


def _get_historical_avg_days(species, breed):
    """Get average days to adoption for similar animals."""
    avg = frappe.db.sql("""
        SELECT AVG(DATEDIFF(outcome_date, intake_date)) as avg_days
        FROM `tabAnimal`
        WHERE status = 'Adopted' AND intake_date IS NOT NULL AND outcome_date IS NOT NULL
          AND species = %s
    """, species, as_dict=True)
    if avg and avg[0].avg_days:
        return flt(avg[0].avg_days)
    # Fallback to overall average
    overall = frappe.db.sql("""
        SELECT AVG(DATEDIFF(outcome_date, intake_date)) as avg_days
        FROM `tabAnimal`
        WHERE status = 'Adopted' AND intake_date IS NOT NULL AND outcome_date IS NOT NULL
    """, as_dict=True)
    return flt(overall[0].avg_days) if overall and overall[0].avg_days else 30


def _generate_adoption_recommendations(animal, factors, score):
    """Generate specific recommendations to improve adoption chances."""
    recs = []

    for f in factors:
        if f["impact"] < 0:
            if f["factor"] == "Photo on file":
                recs.append("📸 Add a high-quality, well-lit photo — animals with photos adopt 3x faster")
            elif f["factor"] == "Age":
                recs.append("👴 Highlight 'senior pet' benefits: calmer, trained, grateful. Consider senior discount")
            elif f["factor"] == "Temperament":
                recs.append("🐕 Work with a trainer on socialization; update assessment after progress")
            elif f["factor"] == "Health status":
                if animal.is_special_needs:
                    recs.append("🏥 Create a detailed special needs care guide for potential adopters")
                if animal.spay_neuter_status not in ("Spayed", "Neutered"):
                    recs.append("✂️ Schedule spay/neuter — pre-fixed animals adopt faster")
            elif f["factor"] == "Compatibility":
                recs.append("🐾 Schedule compatibility assessments if not done")
            elif f["factor"] == "Training":
                recs.append("🎓 Enroll in basic training program; highlight any progress")
            elif f["factor"] == "Length of stay":
                recs.append("📣 Feature in social media spotlight campaign")
                recs.append("💰 Consider reduced adoption fee")
            elif f["factor"] == "Breed appeal":
                recs.append("📝 Emphasize unique personality traits over breed")

    if score < 40 and not recs:
        recs.append("📣 Feature in 'Hard to Place' promotion program")
        recs.append("🏠 Consider foster-to-adopt arrangement")

    return recs[:6]  # Max 6 recommendations
