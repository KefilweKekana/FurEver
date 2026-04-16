"""
Training Progress Tracker — Feature #7
Training analytics, adoption-readiness scoring, and AI-driven training plans.
"""
import frappe
from frappe.utils import today, getdate, flt, cint, date_diff


def get_training_summary(animal_name):
    """Get comprehensive training progress for an animal."""
    records = frappe.get_all("Training Progress", filters={
        "animal": animal_name
    }, fields=["name", "skill", "status", "current_level", "sessions_completed",
               "date_started", "last_session_date", "trainer", "adoption_ready", "notes"],
    order_by="skill asc")

    total = len(records)
    mastered = sum(1 for r in records if r.status == "Mastered")
    proficient = sum(1 for r in records if r.status == "Proficient")
    in_progress = sum(1 for r in records if r.status == "In Progress")

    # Calculate adoption readiness score (0-100)
    essential_skills = ["Sit", "Stay", "Come", "Leash Walking", "House Training", "Crate Training"]
    essential_progress = []
    for skill in essential_skills:
        record = next((r for r in records if r.skill == skill), None)
        if record:
            level_scores = {"Not Started": 0, "In Progress": 25, "Proficient": 75, "Mastered": 100, "Regressed": 15}
            essential_progress.append(level_scores.get(record.status, 0))
        else:
            essential_progress.append(0)

    readiness_score = flt(sum(essential_progress) / max(len(essential_skills), 1), 1)

    return {
        "animal": animal_name,
        "total_skills": total,
        "mastered": mastered,
        "proficient": proficient,
        "in_progress": in_progress,
        "readiness_score": readiness_score,
        "skills": records,
        "adoption_ready": readiness_score >= 60,
        "next_focus": _get_next_focus_skills(records, essential_skills)
    }


def _get_next_focus_skills(records, essential_skills):
    """Determine which skills to focus on next."""
    focus = []
    for skill in essential_skills:
        record = next((r for r in records if r.skill == skill), None)
        if not record:
            focus.append({"skill": skill, "reason": "Not started — essential for adoption"})
        elif record.status in ("Not Started", "In Progress"):
            focus.append({"skill": skill, "reason": f"Currently {record.status} — keep practicing"})
        elif record.status == "Regressed":
            focus.append({"skill": skill, "reason": "⚠️ Regressed — needs refresher sessions"})

    return focus[:3]  # Top 3 priorities


def get_shelter_training_overview():
    """Get training progress overview for all shelter animals."""
    animals = frappe.get_all("Animal", filters={
        "status": ["in", ["Available for Adoption", "Under Evaluation"]]
    }, fields=["name", "animal_name", "species"])

    results = []
    for animal in animals:
        summary = get_training_summary(animal.name)
        results.append({
            "animal": animal.name,
            "animal_name": animal.animal_name,
            "species": animal.species,
            "readiness_score": summary["readiness_score"],
            "adoption_ready": summary["adoption_ready"],
            "skills_mastered": summary["mastered"],
            "total_skills": summary["total_skills"]
        })

    results.sort(key=lambda x: x["readiness_score"], reverse=True)

    return {
        "animals": results,
        "total_animals": len(results),
        "adoption_ready_count": sum(1 for r in results if r["adoption_ready"]),
        "average_readiness": flt(sum(r["readiness_score"] for r in results) / max(len(results), 1), 1)
    }


def get_ai_training_plan(animal_name):
    """Use AI to create a personalized training plan."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_training_tracker", 0):
        return {"error": "Training tracker feature is not enabled"}

    animal = frappe.get_doc("Animal", animal_name)
    summary = get_training_summary(animal_name)

    skills_text = "\n".join([
        f"- {s.skill}: {s.status} (Level: {s.current_level}, Sessions: {s.sessions_completed})"
        for s in summary["skills"]
    ]) or "No training records yet."

    prompt = f"""You are a professional animal trainer. Create a personalized training plan:

Animal: {animal.animal_name}
Species: {animal.species}
Breed: {animal.breed or 'Unknown'}
Age: {animal.estimated_age or 'Unknown'}
Temperament: {animal.temperament or 'Unknown'}
Current Readiness Score: {summary['readiness_score']}/100

Current Training Progress:
{skills_text}

Priority Focus Skills:
{', '.join(f['skill'] for f in summary['next_focus']) or 'None identified'}

Create a 2-week training plan with:
1. Daily schedule (which skills to practice each day)
2. Session duration and method for each skill
3. Milestones to track
4. Tips for volunteer trainers
5. Special considerations based on breed/temperament"""

    from kennel_management.utils.ai_actions import call_llm
    response = call_llm(prompt)
    return {"training_plan": response, "animal": animal_name, "current_readiness": summary["readiness_score"]}
