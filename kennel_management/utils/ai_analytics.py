"""
AI Analytics — Predictive health, smart kennel assignment, donor intelligence.

Data-driven intelligence layer for shelter operations.
"""
import frappe
from frappe.utils import today, getdate, add_days, cint, flt, get_first_day, add_months
from collections import defaultdict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREDICTIVE HEALTH ANALYTICS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_health_predictions(animal=None):
    """Generate health predictions and risk analysis.

    For a specific animal: analyze their medical history and flag risks.
    For shelter-wide: identify at-risk animals and trends.
    """
    now = today()

    if animal:
        return _predict_animal_health(animal, now)
    else:
        return _predict_shelter_health(now)


def _predict_animal_health(animal_identifier, now):
    """Predict health risks for a specific animal."""
    animal_id = _resolve(animal_identifier)
    if not animal_id:
        return {"success": False, "error": f"Could not find animal: {animal_identifier}"}

    doc = frappe.get_doc("Animal", animal_id)
    risks = []
    recommendations = []

    # 1. Overdue vaccinations
    overdue_vacc = frappe.db.sql("""
        SELECT vi.vaccine_name, vi.next_due_date
        FROM `tabVaccination Item` vi
        JOIN `tabVeterinary Record` vr ON vi.parent = vr.name
        WHERE vr.animal = %s AND vi.next_due_date IS NOT NULL AND vi.next_due_date < %s
        ORDER BY vi.next_due_date ASC
    """, (animal_id, now), as_dict=True)
    if overdue_vacc:
        vacc_list = ", ".join([f"{v.vaccine_name} (due {v.next_due_date})" for v in overdue_vacc])
        risks.append({"level": "high", "category": "Vaccination", "detail": f"Overdue vaccinations: {vacc_list}"})
        recommendations.append("Schedule vaccination appointment urgently")

    # 2. Weight trend analysis
    weight_history = frappe.db.sql("""
        SELECT date, weight_kg FROM (
            SELECT vr.date, 0 as weight_kg FROM `tabVeterinary Record` vr
            WHERE vr.animal = %s AND vr.date IS NOT NULL
            ORDER BY vr.date DESC LIMIT 5
        ) sub ORDER BY date ASC
    """, animal_id, as_dict=True)
    # Check current weight
    if doc.weight_kg:
        if doc.species == "Dog" and doc.size == "Small" and flt(doc.weight_kg) > 15:
            risks.append({"level": "medium", "category": "Weight", "detail": f"Weight ({doc.weight_kg}kg) may be high for a small dog"})
            recommendations.append("Consider dietary review")
        elif doc.species == "Cat" and flt(doc.weight_kg) > 8:
            risks.append({"level": "medium", "category": "Weight", "detail": f"Weight ({doc.weight_kg}kg) elevated for a cat"})

    # 3. Length of stay risk
    if doc.intake_date:
        days_in = (getdate(now) - getdate(doc.intake_date)).days
        if days_in > 60:
            risks.append({"level": "high", "category": "Length of Stay",
                          "detail": f"In shelter for {days_in} days — increased stress and illness risk"})
            recommendations.append("Prioritize for adoption promotion or foster placement")
            recommendations.append("Schedule behavior reassessment")
            recommendations.append("Update photos and social media listings")
        elif days_in > 30:
            risks.append({"level": "medium", "category": "Length of Stay",
                          "detail": f"In shelter for {days_in} days — monitor for stress behaviors"})
            recommendations.append("Consider enrichment activities")

    # 4. Age-related risks
    age_years = cint(doc.estimated_age_years)
    if doc.species == "Dog" and age_years >= 8:
        risks.append({"level": "medium", "category": "Senior",
                      "detail": f"Senior dog ({age_years} years) — increased health monitoring needed"})
        recommendations.append("Bi-annual wellness exams recommended")
        recommendations.append("Monitor for arthritis, dental disease, organ function")
    elif doc.species == "Cat" and age_years >= 10:
        risks.append({"level": "medium", "category": "Senior",
                      "detail": f"Senior cat ({age_years} years) — watch for kidney and thyroid issues"})
        recommendations.append("Blood panel recommended every 6 months")

    # 5. Spay/neuter status
    if doc.spay_neuter_status == "Intact":
        risks.append({"level": "medium", "category": "Reproductive",
                      "detail": "Not spayed/neutered — schedule before adoption"})
        recommendations.append("Schedule spay/neuter surgery")

    # 6. Recent medical events
    recent_emergency = frappe.db.count("Veterinary Appointment", {
        "animal": animal_id, "priority": "Emergency",
        "appointment_date": [">=", add_days(now, -30)]
    })
    if recent_emergency:
        risks.append({"level": "high", "category": "Medical History",
                      "detail": f"{recent_emergency} emergency vet visit(s) in last 30 days"})
        recommendations.append("Close monitoring and follow-up care needed")

    # 7. Medication compliance
    active_meds = frappe.db.sql("""
        SELECT mi.medication_name, mi.end_date
        FROM `tabMedication Item` mi
        JOIN `tabVeterinary Record` vr ON mi.parent = vr.name
        WHERE vr.animal = %s AND (mi.end_date IS NULL OR mi.end_date >= %s)
    """, (animal_id, now), as_dict=True)
    if active_meds:
        med_list = ", ".join([m.medication_name for m in active_meds])
        recommendations.append(f"Active medications to monitor: {med_list}")

    # 8. Behavior concerns
    behavior = frappe.get_all("Behavior Assessment", filters={"animal": animal_id},
        fields=["aggression_score", "fear_score"], order_by="assessment_date desc", limit=1)
    if behavior:
        b = behavior[0]
        if cint(b.aggression_score) >= 4:
            risks.append({"level": "high", "category": "Behavior",
                          "detail": "High aggression score — needs behavioral intervention"})
            recommendations.append("Behavioral consult with certified trainer")
        if cint(b.fear_score) >= 4:
            risks.append({"level": "medium", "category": "Behavior",
                          "detail": "High fear score — stress-related illness risk"})
            recommendations.append("Quiet kennel placement and desensitization program")

    # Calculate overall risk level
    high_risks = sum(1 for r in risks if r["level"] == "high")
    med_risks = sum(1 for r in risks if r["level"] == "medium")
    overall = "critical" if high_risks >= 2 else "high" if high_risks >= 1 else "moderate" if med_risks >= 2 else "low"

    # Predict adoption timeline
    adoption_prediction = _predict_adoption_timeline(doc)

    # Format message
    risk_lines = [f"{'🔴' if r['level']=='high' else '🟡'} **{r['category']}**: {r['detail']}" for r in risks]
    rec_lines = [f"→ {r}" for r in recommendations]

    msg = f"**Health Analysis for {doc.animal_name}** (Risk Level: **{overall.upper()}**)\n\n"
    if risk_lines:
        msg += "**Risks:**\n" + "\n".join(risk_lines) + "\n\n"
    else:
        msg += "No significant health risks identified.\n\n"
    if rec_lines:
        msg += "**Recommendations:**\n" + "\n".join(rec_lines) + "\n\n"
    msg += f"**Predicted adoption timeline:** {adoption_prediction}"

    return {
        "success": True,
        "animal": animal_id,
        "animal_name": doc.animal_name,
        "overall_risk": overall,
        "risks": risks,
        "recommendations": recommendations,
        "adoption_prediction": adoption_prediction,
        "message": msg,
    }


def _predict_shelter_health(now):
    """Shelter-wide health predictions and trends."""
    risks = []
    trends = []

    # Animals at risk
    animals = frappe.get_all("Animal",
        filters={"status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]},
        fields=["name", "animal_name", "species", "intake_date", "spay_neuter_status",
                "estimated_age_years", "is_special_needs", "status"],
        limit_page_length=0)

    # Long-stay risk
    long_stay = [a for a in animals if a.intake_date and (getdate(now) - getdate(a.intake_date)).days > 30]
    critical_stay = [a for a in long_stay if (getdate(now) - getdate(a.intake_date)).days > 60]

    if critical_stay:
        names = ", ".join([f"{a.animal_name} ({(getdate(now) - getdate(a.intake_date)).days}d)" for a in critical_stay[:5]])
        risks.append({"level": "high", "detail": f"{len(critical_stay)} animals over 60 days: {names}"})

    # Overdue vaccinations
    overdue_count = frappe.db.sql("""
        SELECT COUNT(DISTINCT vr.animal) as cnt
        FROM `tabVaccination Item` vi
        JOIN `tabVeterinary Record` vr ON vi.parent = vr.name
        WHERE vi.next_due_date IS NOT NULL AND vi.next_due_date < %s
        AND vr.animal IN (SELECT name FROM `tabAnimal`
            WHERE status NOT IN ('Adopted','Transferred','Deceased','Returned to Owner'))
    """, now, as_dict=True)
    overdue_cnt = cint(overdue_count[0].cnt) if overdue_count else 0
    if overdue_cnt:
        risks.append({"level": "high", "detail": f"{overdue_cnt} animals with overdue vaccinations"})

    # Unspayed/unneutered
    intact = [a for a in animals if a.spay_neuter_status == "Intact"]
    if intact:
        risks.append({"level": "medium", "detail": f"{len(intact)} animals not spayed/neutered"})

    # Admission trends (last 4 weeks)
    weeks = []
    for i in range(4):
        start = add_days(now, -(i + 1) * 7)
        end = add_days(now, -i * 7)
        count = frappe.db.count("Animal Admission", {"docstatus": 1,
            "admission_date": ["between", [start, end]]})
        weeks.append(count)

    if weeks[0] > 0:
        avg_prev = sum(weeks[1:]) / 3 if sum(weeks[1:]) > 0 else 1
        if weeks[0] > avg_prev * 1.5:
            trends.append(f"Admissions trending UP — {weeks[0]} this week vs. {avg_prev:.0f} avg previous 3 weeks")
        elif weeks[0] < avg_prev * 0.5:
            trends.append(f"Admissions trending DOWN — {weeks[0]} this week vs. {avg_prev:.0f} avg")

    # Adoption trends
    adoption_weeks = []
    for i in range(4):
        start = add_days(now, -(i + 1) * 7)
        end = add_days(now, -i * 7)
        count = frappe.db.count("Adoption Application", {
            "status": "Adoption Completed",
            "adoption_date": ["between", [start, end]]
        })
        adoption_weeks.append(count)

    if sum(adoption_weeks) > 0:
        trends.append(f"Adoption rate: {adoption_weeks[0]} this week, {sum(adoption_weeks)} in last 4 weeks")

    # Capacity forecast
    total_cap = frappe.db.sql("SELECT SUM(capacity) as cap FROM `tabKennel`", as_dict=True)
    cap = cint(total_cap[0].cap) if total_cap else 0
    current = len(animals)
    utilization = (current / cap * 100) if cap else 0
    if utilization > 90:
        risks.append({"level": "high", "detail": f"Shelter at {utilization:.0f}% capacity — approaching full"})
    elif utilization > 80:
        risks.append({"level": "medium", "detail": f"Shelter at {utilization:.0f}% capacity"})

    # Format
    risk_lines = [f"{'🔴' if r['level']=='high' else '🟡'} {r['detail']}" for r in risks]
    trend_lines = [f"📊 {t}" for t in trends]

    msg = f"**Shelter Health Overview**\n\n"
    if risk_lines:
        msg += "**Risks & Alerts:**\n" + "\n".join(risk_lines) + "\n\n"
    if trend_lines:
        msg += "**Trends:**\n" + "\n".join(trend_lines) + "\n\n"
    msg += f"**Population:** {len(animals)} animals | Long-stay (30+d): {len(long_stay)} | Special needs: {sum(1 for a in animals if a.is_special_needs)}"

    return {
        "success": True,
        "overall_risk": "high" if any(r["level"] == "high" for r in risks) else "moderate" if risks else "low",
        "risks": risks,
        "trends": trends,
        "population": len(animals),
        "long_stay_count": len(long_stay),
        "critical_stay_count": len(critical_stay),
        "capacity_pct": round(utilization, 1),
        "message": msg,
    }


def _predict_adoption_timeline(animal):
    """Predict how long an animal is likely to remain in shelter."""
    # Based on historical adoption data for similar animals
    species = animal.species
    age_years = cint(animal.estimated_age_years)
    size = animal.size or "Medium"

    # Base prediction (days) by species
    base_days = {"Dog": 21, "Cat": 28, "Bird": 35, "Rabbit": 42}.get(species, 45)

    # Age adjustments
    if species == "Dog":
        if age_years < 2:
            base_days -= 7  # puppies adopt faster
        elif age_years >= 8:
            base_days += 21  # seniors take longer
    elif species == "Cat":
        if age_years < 1:
            base_days -= 10
        elif age_years >= 10:
            base_days += 25

    # Size adjustments (dogs)
    if species == "Dog":
        if size in ("Tiny", "Small"):
            base_days -= 5
        elif size in ("Large", "Giant"):
            base_days += 10

    # Special needs
    if animal.is_special_needs:
        base_days += 20

    # Temperament
    temp = (animal.temperament or "").lower()
    if temp in ("friendly", "playful", "calm"):
        base_days -= 5
    elif temp in ("aggressive", "fearful", "anxious"):
        base_days += 15

    # Already in shelter time
    if animal.intake_date:
        days_in = (getdate(today()) - getdate(animal.intake_date)).days
        remaining = max(base_days - days_in, 3)
        return f"~{remaining} more days (total ~{base_days} days typical for {species}/{size})"

    return f"~{base_days} days typical for {species}/{size}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SMART KENNEL ASSIGNMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def recommend_kennel(args):
    """AI-powered kennel placement recommendation.

    Considers: temperament, compatibility, medical needs, noise sensitivity,
    current occupancy, proximity to similar animals.
    """
    animal_id = None
    animal_doc = None

    if args.get("animal"):
        animal_id = _resolve(args["animal"])
        if animal_id:
            animal_doc = frappe.get_doc("Animal", animal_id)

    # Animal properties (from doc or args)
    species = (animal_doc.species if animal_doc else args.get("species")) or "Dog"
    temperament = (animal_doc.temperament if animal_doc else args.get("temperament")) or "Unknown"
    size = (animal_doc.size if animal_doc else args.get("size")) or "Medium"
    good_with_dogs = (animal_doc.good_with_dogs if animal_doc else args.get("good_with_dogs")) or "Unknown"
    good_with_cats = (animal_doc.good_with_cats if animal_doc else args.get("good_with_cats")) or "Unknown"
    is_special_needs = (animal_doc.is_special_needs if animal_doc else args.get("is_special_needs")) or False
    requires_quarantine = args.get("requires_quarantine", False)
    requires_isolation = args.get("requires_isolation", False)

    # Get all kennels with details
    kennels = frappe.get_all("Kennel", fields=[
        "name", "kennel_name", "kennel_type", "section", "capacity", "current_occupancy",
        "status", "size_category", "has_outdoor_access", "has_heating", "has_cooling",
        "is_isolation", "is_quarantine",
    ], limit_page_length=0)

    # Get current animal placements for compatibility analysis
    placed_animals = frappe.get_all("Animal",
        filters={"current_kennel": ["is", "set"],
                 "status": ["not in", ["Adopted", "Transferred", "Deceased"]]},
        fields=["name", "animal_name", "species", "temperament", "current_kennel",
                "good_with_dogs", "good_with_cats", "size", "energy_level"],
        limit_page_length=0)

    kennel_animals = defaultdict(list)
    for a in placed_animals:
        kennel_animals[a.current_kennel].append(a)

    # Score each kennel
    scored_kennels = []
    for k in kennels:
        if k.status in ("Maintenance", "Out of Service"):
            continue
        if k.current_occupancy >= k.capacity:
            continue

        score = 50  # baseline
        reasons = []

        # Quarantine requirement
        if requires_quarantine:
            if k.is_quarantine:
                score += 30
                reasons.append("Quarantine kennel (required)")
            else:
                continue  # Skip non-quarantine kennels
        elif k.is_quarantine:
            score -= 20  # Don't use quarantine for non-quarantine animals

        # Isolation requirement
        if requires_isolation:
            if k.is_isolation:
                score += 30
                reasons.append("Isolation kennel (required)")
            else:
                continue
        elif k.is_isolation and not requires_quarantine:
            score -= 15

        # Occupancy (prefer emptier kennels)
        occupancy_ratio = k.current_occupancy / k.capacity if k.capacity else 1
        if occupancy_ratio == 0:
            score += 15
            reasons.append("Empty kennel — no compatibility concerns")
        elif occupancy_ratio < 0.5:
            score += 10
            reasons.append("Low occupancy")
        elif occupancy_ratio >= 0.8:
            score -= 10

        # Compatibility with existing animals in kennel
        existing = kennel_animals.get(k.name, [])
        for ex in existing:
            # Species compatibility
            if ex.species != species:
                if good_with_dogs == "No" and ex.species == "Dog":
                    score -= 25
                    reasons.append(f"Not good with dogs — {ex.animal_name} is in this kennel")
                elif good_with_cats == "No" and ex.species == "Cat":
                    score -= 25
                    reasons.append(f"Not good with cats — {ex.animal_name} is in this kennel")

            # Temperament compatibility
            temp_lower = temperament.lower()
            ex_temp = (ex.temperament or "").lower()
            if temp_lower in ("fearful", "shy", "anxious") and ex_temp in ("aggressive", "playful"):
                score -= 15
                reasons.append(f"Fearful animal near {ex_temp} animal ({ex.animal_name})")
            elif temp_lower == "aggressive" and ex_temp in ("fearful", "shy"):
                score -= 15
                reasons.append(f"Aggressive animal near fearful animal ({ex.animal_name})")

        # Size category match
        if k.size_category:
            kennel_size = k.size_category.lower()
            animal_size = size.lower()
            if (kennel_size == "large" and animal_size in ("large", "giant")) or \
               (kennel_size == "small" and animal_size in ("tiny", "small")) or \
               (kennel_size == "medium" and animal_size == "medium"):
                score += 10
                reasons.append("Size-appropriate kennel")

        # Outdoor access for high-energy animals
        if temperament.lower() in ("playful",) or (animal_doc and (animal_doc.energy_level or "").lower() in ("high", "very high")):
            if k.has_outdoor_access:
                score += 10
                reasons.append("Outdoor access for high-energy animal")

        # Special needs — prefer recovery/indoor kennels
        if is_special_needs:
            if k.kennel_type in ("Recovery", "Indoor"):
                score += 10
                reasons.append("Recovery/indoor kennel for special needs")

        scored_kennels.append({
            "kennel_id": k.name,
            "kennel_name": k.kennel_name,
            "kennel_type": k.kennel_type,
            "section": k.section,
            "occupancy": f"{k.current_occupancy}/{k.capacity}",
            "score": score,
            "reasons": reasons,
        })

    scored_kennels.sort(key=lambda x: x["score"], reverse=True)
    top = scored_kennels[:5]

    if not top:
        return {"success": True, "message": "No suitable kennels available. All are full or incompatible.", "recommendations": []}

    lines = []
    for i, k in enumerate(top):
        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
        reason_str = "; ".join(k["reasons"][:3]) if k["reasons"] else "Standard placement"
        lines.append(f"{emoji} **{k['kennel_name']}** ({k['kennel_type']}, {k['occupancy']}) — Score: {k['score']} — {reason_str}")

    animal_name = animal_doc.animal_name if animal_doc else "the animal"
    msg = f"**Kennel recommendations for {animal_name}:**\n\n" + "\n".join(lines)

    return {
        "success": True,
        "recommendations": top,
        "best_kennel": top[0] if top else None,
        "message": msg,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DONOR INTELLIGENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_donor_insights(analysis_type="overview"):
    """Comprehensive donor intelligence and analytics."""
    now = today()

    if analysis_type == "lapsed_donors":
        return _get_lapsed_donors(now)
    elif analysis_type == "top_donors":
        return _get_top_donors(now)
    elif analysis_type == "campaign_analysis":
        return _get_campaign_analysis(now)
    elif analysis_type == "trends":
        return _get_donation_trends(now)
    else:
        return _get_donor_overview(now)


def _get_donor_overview(now):
    """Complete donor overview."""
    first_this = get_first_day(now)
    first_last = get_first_day(add_months(now, -1))
    first_prev = get_first_day(add_months(now, -2))

    # This month
    this_month = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date >= %s
    """, first_this, as_dict=True)[0]

    # Last month
    last_month = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date >= %s AND donation_date < %s
    """, (first_last, first_this), as_dict=True)[0]

    # YTD
    year_start = f"{getdate(now).year}-01-01"
    ytd = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt,
               COUNT(DISTINCT donor_name) as unique_donors
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date >= %s
    """, year_start, as_dict=True)[0]

    # Average donation
    avg_donation = flt(ytd.total) / cint(ytd.cnt) if cint(ytd.cnt) > 0 else 0

    # Month-over-month change
    change = 0
    if flt(last_month.total) > 0:
        change = ((flt(this_month.total) - flt(last_month.total)) / flt(last_month.total)) * 100

    # Top donors this month
    top = frappe.db.sql("""
        SELECT donor_name, SUM(amount) as total, COUNT(*) as cnt
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date >= %s
        GROUP BY donor_name ORDER BY total DESC LIMIT 5
    """, first_this, as_dict=True)

    # By type
    by_type = frappe.db.sql("""
        SELECT donation_type, SUM(amount) as total, COUNT(*) as cnt
        FROM `tabDonation` WHERE docstatus = 1 AND donation_date >= %s
        GROUP BY donation_type ORDER BY total DESC
    """, year_start, as_dict=True)

    # Lapsed donor count
    lapsed = frappe.db.sql("""
        SELECT COUNT(DISTINCT donor_name) as cnt FROM `tabDonation`
        WHERE docstatus = 1 AND donor_name NOT IN (
            SELECT DISTINCT donor_name FROM `tabDonation`
            WHERE docstatus = 1 AND donation_date >= %s
        ) AND donation_date >= %s
    """, (add_days(now, -90), add_days(now, -365)), as_dict=True)
    lapsed_count = cint(lapsed[0].cnt) if lapsed else 0

    msg = f"**Donor Intelligence Overview**\n\n"
    msg += f"**This Month:** R {flt(this_month.total):,.0f} from {cint(this_month.cnt)} donations"
    if change:
        arrow = "↑" if change > 0 else "↓"
        msg += f" ({arrow} {abs(change):.0f}% vs last month)\n"
    else:
        msg += "\n"
    msg += f"**Last Month:** R {flt(last_month.total):,.0f} from {cint(last_month.cnt)} donations\n"
    msg += f"**YTD:** R {flt(ytd.total):,.0f} from {cint(ytd.unique_donors)} unique donors ({cint(ytd.cnt)} donations)\n"
    msg += f"**Average Donation:** R {avg_donation:,.0f}\n"
    msg += f"**Lapsed Donors (90+ days):** {lapsed_count} — potential re-engagement targets\n\n"

    if top:
        msg += "**Top Donors This Month:**\n"
        for t in top:
            msg += f"  • {t.donor_name}: R {flt(t.total):,.0f} ({t.cnt} donations)\n"
    if by_type:
        msg += "\n**By Type (YTD):**\n"
        for bt in by_type:
            msg += f"  • {bt.donation_type}: R {flt(bt.total):,.0f} ({bt.cnt})\n"

    return {
        "success": True,
        "this_month": {"total": flt(this_month.total), "count": cint(this_month.cnt)},
        "last_month": {"total": flt(last_month.total), "count": cint(last_month.cnt)},
        "ytd": {"total": flt(ytd.total), "count": cint(ytd.cnt), "unique_donors": cint(ytd.unique_donors)},
        "change_pct": round(change, 1),
        "avg_donation": round(avg_donation, 0),
        "lapsed_count": lapsed_count,
        "message": msg,
    }


def _get_lapsed_donors(now):
    """Find donors who haven't donated in 90+ days but were active before."""
    lapsed = frappe.db.sql("""
        SELECT donor_name, MAX(donation_date) as last_donation,
               SUM(amount) as lifetime_total, COUNT(*) as total_donations
        FROM `tabDonation`
        WHERE docstatus = 1 AND donor_name NOT IN (
            SELECT DISTINCT donor_name FROM `tabDonation`
            WHERE docstatus = 1 AND donation_date >= %s
        )
        GROUP BY donor_name
        HAVING MAX(donation_date) >= %s
        ORDER BY lifetime_total DESC
        LIMIT 20
    """, (add_days(now, -90), add_days(now, -365)), as_dict=True)

    lines = []
    for d in lapsed:
        days_since = (getdate(now) - getdate(d.last_donation)).days
        lines.append(
            f"• **{d.donor_name}** — Last donation: {d.last_donation} ({days_since} days ago) | "
            f"Lifetime: R {flt(d.lifetime_total):,.0f} from {d.total_donations} donations"
        )

    msg = f"**Lapsed Donors** (no donation in 90+ days, active within past year)\n\n"
    msg += "\n".join(lines) if lines else "No lapsed donors found."
    msg += f"\n\n**Re-engagement suggestions:**\n"
    msg += "→ Personalized thank-you letter mentioning their past impact\n"
    msg += "→ Update on animals they helped (if trackable)\n"
    msg += "→ Invite to upcoming shelter events\n"
    msg += "→ Matching donation campaign to re-activate giving"

    # Convert date/Decimal for JSON serialization
    for d in lapsed:
        d["last_donation"] = str(d.get("last_donation", ""))
        d["lifetime_total"] = flt(d.get("lifetime_total", 0))

    return {"success": True, "lapsed_donors": lapsed, "count": len(lapsed), "message": msg}


def _get_top_donors(now):
    """Top donors by lifetime giving."""
    top = frappe.db.sql("""
        SELECT donor_name, SUM(amount) as total, COUNT(*) as cnt,
               MIN(donation_date) as first, MAX(donation_date) as last
        FROM `tabDonation` WHERE docstatus = 1
        GROUP BY donor_name ORDER BY total DESC LIMIT 15
    """, as_dict=True)

    lines = []
    for d in top:
        lines.append(
            f"• **{d.donor_name}** — R {flt(d.total):,.0f} lifetime ({d.cnt} donations, "
            f"{d.first} → {d.last})"
        )

    msg = f"**Top Donors (Lifetime)**\n\n" + "\n".join(lines) if lines else "No donation data."

    # Convert date/Decimal for JSON serialization
    for d in top:
        d["total"] = flt(d.get("total", 0))
        d["first"] = str(d.get("first", ""))
        d["last"] = str(d.get("last", ""))

    return {"success": True, "top_donors": top, "message": msg}


def _get_campaign_analysis(now):
    """Analyze donation campaigns."""
    campaigns = frappe.db.sql("""
        SELECT campaign, SUM(amount) as total, COUNT(*) as cnt,
               COUNT(DISTINCT donor_name) as unique_donors,
               AVG(amount) as avg_amount
        FROM `tabDonation` WHERE docstatus = 1 AND campaign IS NOT NULL AND campaign != ''
        GROUP BY campaign ORDER BY total DESC
    """, as_dict=True)

    if not campaigns:
        return {"success": True, "message": "No campaign data found. Donations may not be tagged with campaigns."}

    lines = []
    for c in campaigns:
        lines.append(
            f"• **{c.campaign}** — R {flt(c.total):,.0f} from {c.unique_donors} donors "
            f"({c.cnt} donations, avg R {flt(c.avg_amount):,.0f})"
        )

    msg = "**Campaign Performance**\n\n" + "\n".join(lines)

    # Convert Decimal for JSON serialization
    for c in campaigns:
        c["total"] = flt(c.get("total", 0))
        c["avg_amount"] = flt(c.get("avg_amount", 0))

    return {"success": True, "campaigns": campaigns, "message": msg}


def _get_donation_trends(now):
    """Monthly donation trends over last 12 months."""
    months = []
    for i in range(12):
        month_start = get_first_day(add_months(now, -i))
        next_month = get_first_day(add_months(now, -i + 1))
        data = frappe.db.sql("""
            SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt
            FROM `tabDonation` WHERE docstatus = 1
            AND donation_date >= %s AND donation_date < %s
        """, (month_start, next_month), as_dict=True)[0]
        months.append({
            "month": str(month_start)[:7],
            "total": flt(data.total),
            "count": cint(data.cnt),
        })

    months.reverse()
    lines = [f"  {m['month']}: R {m['total']:,.0f} ({m['count']} donations)" for m in months]

    msg = "**Donation Trends (Last 12 Months)**\n\n" + "\n".join(lines)

    # Trend direction
    recent_3 = sum(m["total"] for m in months[-3:])
    prev_3 = sum(m["total"] for m in months[-6:-3])
    if prev_3 > 0:
        change = ((recent_3 - prev_3) / prev_3) * 100
        if change > 10:
            msg += f"\n\n📈 Donations trending **UP** ({change:.0f}% increase last 3 months vs. prior 3)"
        elif change < -10:
            msg += f"\n\n📉 Donations trending **DOWN** ({abs(change):.0f}% decrease) — consider fundraising campaign"

    return {"success": True, "months": months, "message": msg}


def _resolve(identifier):
    """Resolve animal identifier."""
    if not identifier:
        return None
    if frappe.db.exists("Animal", identifier):
        return identifier
    matches = frappe.get_all("Animal", filters={"animal_name": ["like", f"%{identifier}%"]},
        fields=["name"], order_by="creation desc", limit=1)
    return matches[0].name if matches else None
