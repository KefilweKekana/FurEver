"""
Smart Volunteer Scheduling — Feature #8
Match volunteer skills/availability to shelter needs, suggest optimal
shift assignments, and track volunteer engagement.
"""
import frappe
from frappe.utils import today, add_days, getdate, cint, flt, get_weekday


SKILL_TASK_MAP = {
    "Dog Walking": ["dog_walking", "exercise"],
    "Cat Socialization": ["cat_socializing", "enrichment"],
    "Animal Grooming": ["grooming", "bathing"],
    "Photography": ["photography", "social_media"],
    "Administrative": ["admin", "data_entry", "phones"],
    "Cleaning": ["cleaning", "kennel_maintenance"],
    "Fundraising": ["fundraising", "events"],
    "Transport": ["transport", "vet_runs"],
    "Training": ["dog_training", "behavior"],
    "Medical Assistance": ["vet_assist", "medication"],
    "Foster Coordination": ["foster", "home_checks"],
    "Event Planning": ["events", "adoption_days"],
    "Social Media": ["social_media", "photography", "content"],
}


def get_volunteer_schedule_suggestions():
    """Generate smart volunteer scheduling suggestions based on current needs and availability."""
    now = today()
    weekday = get_weekday(getdate(now))  # 0=Monday .. 6=Sunday
    day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]

    # Get active volunteers with their availability
    volunteers = frappe.get_all("Volunteer",
        filters={"status": "Active"},
        fields=["name", "full_name", "email", "available_days", "available_shift",
                "skills", "interests", "hours_per_week", "total_hours_volunteered"],
        order_by="full_name", limit_page_length=0)

    # Filter to today-available volunteers
    available_today = []
    for v in volunteers:
        days = (v.available_days or "").lower()
        if day_name.lower() in days or "any" in days or "all" in days:
            available_today.append(v)

    # Determine shelter needs
    needs = _assess_shelter_needs(now)

    # Match volunteers to needs
    assignments = _match_volunteers_to_needs(available_today, needs)

    # Format response
    return {
        "success": True,
        "date": now,
        "day": day_name,
        "available_volunteers": len(available_today),
        "total_active": len(volunteers),
        "needs": needs,
        "assignments": assignments,
        "message": _format_schedule_message(day_name, now, available_today, needs, assignments),
    }


def _assess_shelter_needs(now):
    """Determine today's shelter volunteer needs based on current state."""
    needs = []

    # Dog walking needs — based on current dog count
    dog_count = frappe.db.count("Animal", {
        "species": "Dog",
        "status": ["in", ["Available for Adoption", "Stray Hold", "In Foster Care", "Behavior Hold"]],
    })
    if dog_count > 0:
        walks_needed = max(1, dog_count // 5)  # 1 walker per 5 dogs
        needs.append({
            "task": "Dog Walking",
            "priority": "High" if dog_count > 15 else "Medium",
            "slots_needed": walks_needed,
            "skills_wanted": ["Dog Walking", "Training"],
            "shift": "Morning",
            "detail": f"{dog_count} dogs need exercise",
        })

    # Cat socialization
    cat_count = frappe.db.count("Animal", {
        "species": "Cat",
        "status": ["in", ["Available for Adoption", "Stray Hold"]],
    })
    if cat_count > 0:
        needs.append({
            "task": "Cat Socialization",
            "priority": "Medium",
            "slots_needed": max(1, cat_count // 8),
            "skills_wanted": ["Cat Socialization"],
            "shift": "Any",
            "detail": f"{cat_count} cats benefit from socialization",
        })

    # Kennel cleaning
    occupied = frappe.db.sql("""
        SELECT COUNT(*) as cnt FROM `tabKennel`
        WHERE current_occupancy > 0 AND status = 'Available'
    """, as_dict=True)
    kennel_cnt = cint(occupied[0].cnt) if occupied else 0
    if kennel_cnt > 0:
        needs.append({
            "task": "Kennel Cleaning",
            "priority": "High",
            "slots_needed": max(1, kennel_cnt // 10),
            "skills_wanted": ["Cleaning"],
            "shift": "Morning",
            "detail": f"{kennel_cnt} occupied kennels need daily cleaning",
        })

    # Adoption events — check if any pending applications need processing
    pending_apps = frappe.db.count("Adoption Application", {"status": ["in", ["Pending", "Under Review"]]})
    if pending_apps > 5:
        needs.append({
            "task": "Adoption Counseling",
            "priority": "High",
            "slots_needed": max(1, pending_apps // 5),
            "skills_wanted": ["Administrative", "Foster Coordination"],
            "shift": "Any",
            "detail": f"{pending_apps} adoption applications pending review",
        })

    # Photography — animals without photos
    no_photo = frappe.db.count("Animal", {
        "status": "Available for Adoption",
        "animal_photo": ["is", "not set"],
    })
    if no_photo > 0:
        needs.append({
            "task": "Animal Photography",
            "priority": "Medium" if no_photo > 5 else "Low",
            "slots_needed": 1,
            "skills_wanted": ["Photography", "Social Media"],
            "shift": "Any",
            "detail": f"{no_photo} animals need adoption photos",
        })

    # Medical assistance — check vet appointments today
    vet_count = frappe.db.count("Veterinary Appointment", {
        "appointment_date": now,
        "status": ["!=", "Cancelled"],
    })
    if vet_count > 3:
        needs.append({
            "task": "Veterinary Assistance",
            "priority": "High",
            "slots_needed": max(1, vet_count // 4),
            "skills_wanted": ["Medical Assistance"],
            "shift": "Morning",
            "detail": f"{vet_count} vet appointments today",
        })

    # Feeding rounds
    needs.append({
        "task": "Feeding Rounds",
        "priority": "High",
        "slots_needed": 2,
        "skills_wanted": ["Cleaning"],  # Anyone can help
        "shift": "Morning",
        "detail": "Morning and afternoon feeding rounds",
    })

    return sorted(needs, key=lambda n: {"High": 0, "Medium": 1, "Low": 2}.get(n["priority"], 3))


def _match_volunteers_to_needs(volunteers, needs):
    """Match available volunteers to shelter needs based on skills."""
    assignments = []
    assigned_volunteers = set()

    for need in needs:
        matched = []
        for v in volunteers:
            if v.name in assigned_volunteers:
                continue

            vol_skills = (v.skills or "").split(",") if v.skills else []
            vol_skills = [s.strip() for s in vol_skills]
            vol_interests = (v.interests or "").lower()

            # Check skill match
            skill_match = any(s in vol_skills for s in need["skills_wanted"])
            interest_match = any(s.lower() in vol_interests for s in need["skills_wanted"])

            # Check shift compatibility
            vol_shift = (v.available_shift or "Any").lower()
            need_shift = need["shift"].lower()
            shift_ok = vol_shift in ("any", need_shift) or need_shift == "any"

            if (skill_match or interest_match) and shift_ok:
                matched.append({
                    "volunteer_id": v.name,
                    "volunteer_name": v.full_name,
                    "email": v.email,
                    "match_type": "Skill" if skill_match else "Interest",
                    "shift": v.available_shift or "Any",
                })
                assigned_volunteers.add(v.name)

                if len(matched) >= need["slots_needed"]:
                    break

        assignments.append({
            "task": need["task"],
            "priority": need["priority"],
            "slots_needed": need["slots_needed"],
            "slots_filled": len(matched),
            "volunteers": matched,
            "shortfall": max(0, need["slots_needed"] - len(matched)),
        })

    # Assign remaining volunteers to general duties
    unassigned = [v for v in volunteers if v.name not in assigned_volunteers]
    if unassigned:
        assignments.append({
            "task": "General Support",
            "priority": "Low",
            "slots_needed": 0,
            "slots_filled": len(unassigned),
            "volunteers": [{"volunteer_id": v.name, "volunteer_name": v.full_name,
                           "email": v.email, "match_type": "Available", "shift": v.available_shift or "Any"}
                          for v in unassigned],
            "shortfall": 0,
        })

    return assignments


def _format_schedule_message(day_name, now, available, needs, assignments):
    """Format the schedule into a readable message."""
    lines = [f"**📋 Volunteer Schedule — {day_name}, {now}**\n",
             f"👥 **{len(available)} volunteers** available today\n"]

    for a in assignments:
        icon = "🔴" if a["priority"] == "High" else "🟡" if a["priority"] == "Medium" else "🟢"
        status = "✅" if a["shortfall"] == 0 else f"⚠️ Need {a['shortfall']} more"
        lines.append(f"\n{icon} **{a['task']}** — {status}")

        for v in a["volunteers"]:
            lines.append(f"  → {v['volunteer_name']} ({v['match_type']} match, {v['shift']} shift)")

        if a["shortfall"] > 0:
            lines.append(f"  ❗ {a['shortfall']} unfilled slot(s)")

    # Summary
    total_slots = sum(a["slots_needed"] for a in assignments if a["task"] != "General Support")
    filled_slots = sum(a["slots_filled"] for a in assignments if a["task"] != "General Support")
    lines.append(f"\n📊 **Coverage:** {filled_slots}/{total_slots} slots filled")

    if any(a["shortfall"] > 0 for a in assignments):
        lines.append("💡 **Tip:** Share unfilled shifts on the volunteer WhatsApp group")

    return "\n".join(lines)


def get_volunteer_engagement_report():
    """Analyze volunteer engagement patterns and suggest improvements."""
    volunteers = frappe.get_all("Volunteer",
        filters={"status": "Active"},
        fields=["name", "full_name", "total_hours_volunteered", "skills",
                "creation", "available_days", "hours_per_week"],
        order_by="total_hours_volunteered desc", limit_page_length=0)

    if not volunteers:
        return {"success": True, "message": "No active volunteers found."}

    total_vols = len(volunteers)
    total_hours = sum(flt(v.total_hours_volunteered) for v in volunteers)
    avg_hours = round(total_hours / total_vols, 1) if total_vols else 0

    # Top volunteers
    top = volunteers[:5]
    # Potentially disengaging (0 hours or very low)
    low_engagement = [v for v in volunteers if flt(v.total_hours_volunteered) < 5]

    lines = ["**📊 Volunteer Engagement Report**\n",
             f"👥 Active volunteers: **{total_vols}**",
             f"⏱️ Total hours contributed: **{total_hours:,.0f}**",
             f"📈 Average hours/volunteer: **{avg_hours}**\n"]

    if top:
        lines.append("🌟 **Top Volunteers:**")
        for v in top:
            lines.append(f"  • {v.full_name} — {flt(v.total_hours_volunteered):,.0f} hours")

    if low_engagement:
        lines.append(f"\n⚠️ **{len(low_engagement)} volunteers** with < 5 hours — may need re-engagement")
        for v in low_engagement[:5]:
            lines.append(f"  • {v.full_name} — {flt(v.total_hours_volunteered):,.0f} hours")

    # Skill gaps
    all_skills = {}
    for v in volunteers:
        for s in (v.skills or "").split(","):
            s = s.strip()
            if s:
                all_skills[s] = all_skills.get(s, 0) + 1

    if all_skills:
        lines.append("\n🔧 **Skills Inventory:**")
        for skill, count in sorted(all_skills.items(), key=lambda x: x[1], reverse=True)[:8]:
            lines.append(f"  • {skill}: {count} volunteer{'s' if count != 1 else ''}")

    return {
        "success": True,
        "total_volunteers": total_vols,
        "total_hours": total_hours,
        "avg_hours": avg_hours,
        "top_volunteers": [{"name": v.full_name, "hours": flt(v.total_hours_volunteered)} for v in top],
        "low_engagement_count": len(low_engagement),
        "message": "\n".join(lines),
    }
