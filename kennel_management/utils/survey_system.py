"""
Automated Adoption Follow-Up Surveys — Feature #12
Survey generation, sending, return-risk detection, and analytics.
"""
import frappe
from frappe.utils import today, add_days, getdate, flt, cint, date_diff


SURVEY_MILESTONES = {
    "1 Week": 7,
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
}


def generate_pending_surveys():
    """Daily task: create survey records for adopted animals at milestone dates."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_follow_up_surveys", 0):
        return {"status": "disabled"}

    now = getdate(today())
    created = 0

    # Get all approved adoptions
    adoptions = frappe.get_all("Adoption Application", filters={
        "status": "Approved"
    }, fields=["name", "animal", "animal_name", "applicant_name", "email_address",
               "approval_date", "modified"])

    for app in adoptions:
        adoption_date = getdate(app.approval_date or app.modified)

        for milestone, days in SURVEY_MILESTONES.items():
            survey_date = add_days(adoption_date, days)

            # Only create if we're within 3 days of the milestone
            days_until = date_diff(survey_date, now)
            if days_until < -3 or days_until > 3:
                continue

            # Check if survey already exists
            exists = frappe.db.exists("Adoption Survey", {
                "adoption_application": app.name,
                "milestone": milestone
            })
            if exists:
                continue

            doc = frappe.get_doc({
                "doctype": "Adoption Survey",
                "adoption_application": app.name,
                "adopter_name": app.applicant_name,
                "adopter_email": app.email_address,
                "animal": app.animal,
                "animal_name": app.animal_name,
                "milestone": milestone,
                "status": "Pending",
                "sent_date": today()
            })
            doc.insert(ignore_permissions=True)
            created += 1

            # Send survey email
            if app.email_address:
                _send_survey_email(doc, app)

    frappe.db.commit()
    return {"surveys_created": created}


def _send_survey_email(survey, adoption):
    """Send survey email to adopter."""
    survey_url = frappe.utils.get_url(f"/api/method/kennel_management.api.submit_adoption_survey?survey={survey.name}")

    try:
        frappe.sendmail(
            recipients=[survey.adopter_email],
            subject=f"How is {survey.animal_name} doing? ({survey.milestone} Check-In)",
            message=f"""
            <h2>🐾 {survey.milestone} Check-In</h2>
            <p>Dear {survey.adopter_name},</p>
            <p>It's been {survey.milestone.lower()} since you adopted <strong>{survey.animal_name}</strong>!
            We'd love to hear how things are going.</p>

            <p>Please take a moment to fill out this short survey — it helps us improve
            our adoption process and ensure every pet finds their perfect home.</p>

            <p style="text-align: center; margin: 20px 0;">
                <a href="{survey_url}" style="background: #4CAF50; color: white; padding: 12px 24px;
                   text-decoration: none; border-radius: 5px; font-size: 16px;">
                    Fill Out Survey
                </a>
            </p>

            <p>If you're experiencing any challenges, please don't hesitate to reach out.
            We're here to help!</p>

            <p>Warm regards,<br>The Shelter Team</p>
            """,
            now=True
        )
        survey.status = "Sent"
        survey.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(f"Failed to send survey to {survey.adopter_email}")


def process_survey_response(survey_name, responses):
    """Process a completed survey and calculate risk score.

    Args:
        survey_name: Name of the Adoption Survey record
        responses: dict with satisfaction, health_rating, behavior_rating,
                   would_recommend, considering_return, challenges, positive, comments
    """
    survey = frappe.get_doc("Adoption Survey", survey_name)

    survey.overall_satisfaction = flt(responses.get("overall_satisfaction", 0))
    survey.health_rating = flt(responses.get("health_rating", 0))
    survey.behavior_rating = flt(responses.get("behavior_rating", 0))
    survey.would_recommend = responses.get("would_recommend", "")
    survey.considering_return = cint(responses.get("considering_return", 0))
    survey.challenges = responses.get("challenges", "")
    survey.positive_experiences = responses.get("positive_experiences", "")
    survey.additional_comments = responses.get("additional_comments", "")
    survey.completed_date = today()
    survey.status = "Completed"

    # Calculate risk score
    risk = _calculate_return_risk(survey)
    survey.risk_score = risk

    survey.save(ignore_permissions=True)

    # Trigger urgent follow-up if high risk
    if risk >= 70 or survey.considering_return:
        _create_urgent_followup(survey)

    frappe.db.commit()
    return {"status": "success", "risk_score": risk}


def _calculate_return_risk(survey):
    """Calculate return risk score (0-100) based on survey responses."""
    risk = 0

    # Considering return is the biggest red flag
    if survey.considering_return:
        risk += 50

    # Low satisfaction
    if flt(survey.overall_satisfaction) <= 0.2:
        risk += 20
    elif flt(survey.overall_satisfaction) <= 0.4:
        risk += 10

    # Low behavior rating
    if flt(survey.behavior_rating) <= 0.2:
        risk += 15
    elif flt(survey.behavior_rating) <= 0.4:
        risk += 8

    # Low health rating
    if flt(survey.health_rating) <= 0.2:
        risk += 10

    # Would not recommend
    rec = (survey.would_recommend or "").lower()
    if "not" in rec or "no" in rec:
        risk += 10

    # Challenges mentioned
    if survey.challenges and len(survey.challenges) > 50:
        risk += 5

    return min(risk, 100)


def _create_urgent_followup(survey):
    """Create an urgent ToDo for high-risk survey responses."""
    managers = frappe.get_all("Has Role", filters={"role": "Kennel Manager"}, fields=["parent"])

    for m in managers:
        frappe.get_doc({
            "doctype": "ToDo",
            "description": (
                f"🚨 **Urgent Follow-Up Required** — {survey.adopter_name} "
                f"(adopted {survey.animal_name})\n\n"
                f"Milestone: {survey.milestone}\n"
                f"Risk Score: {survey.risk_score}/100\n"
                f"Considering Return: {'YES ⚠️' if survey.considering_return else 'No'}\n"
                f"Challenges: {survey.challenges or 'None listed'}\n\n"
                f"Please reach out to the adopter immediately."
            ),
            "reference_type": "Adoption Survey",
            "reference_name": survey.name,
            "allocated_to": m.parent,
            "priority": "High",
        }).insert(ignore_permissions=True)


def get_survey_analytics():
    """Get analytics across all completed surveys."""
    surveys = frappe.get_all("Adoption Survey", filters={
        "status": "Completed"
    }, fields=["milestone", "overall_satisfaction", "health_rating", "behavior_rating",
               "would_recommend", "considering_return", "risk_score"])

    if not surveys:
        return {"total": 0, "message": "No completed surveys yet"}

    total = len(surveys)
    avg_satisfaction = flt(sum(flt(s.overall_satisfaction) for s in surveys) / total, 2)
    avg_risk = flt(sum(cint(s.risk_score) for s in surveys) / total, 1)
    returns_considering = sum(1 for s in surveys if s.considering_return)

    # By milestone
    by_milestone = {}
    for s in surveys:
        m = s.milestone
        if m not in by_milestone:
            by_milestone[m] = {"count": 0, "avg_satisfaction": 0, "avg_risk": 0}
        by_milestone[m]["count"] += 1
        by_milestone[m]["avg_satisfaction"] += flt(s.overall_satisfaction)
        by_milestone[m]["avg_risk"] += cint(s.risk_score)

    for m in by_milestone:
        c = by_milestone[m]["count"]
        by_milestone[m]["avg_satisfaction"] = flt(by_milestone[m]["avg_satisfaction"] / c, 2)
        by_milestone[m]["avg_risk"] = flt(by_milestone[m]["avg_risk"] / c, 1)

    return {
        "total_completed": total,
        "average_satisfaction": avg_satisfaction,
        "average_risk_score": avg_risk,
        "considering_return": returns_considering,
        "return_risk_rate": flt(returns_considering / total * 100, 1),
        "by_milestone": by_milestone
    }
