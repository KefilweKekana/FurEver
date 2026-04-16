"""
Donation Campaign Builder — Feature #9
AI-powered story generation, campaign analytics, and progress tracking.
"""
import frappe
from frappe.utils import today, getdate, flt, cint, add_days


def get_campaign_dashboard():
    """Get overview of all donation campaigns."""
    campaigns = frappe.get_all("Donation Campaign", filters={
        "status": ["in", ["Active", "Paused"]]
    }, fields=["name", "campaign_name", "campaign_type", "status", "start_date",
               "end_date", "goal_amount", "amount_raised", "donor_count", "progress_percent",
               "featured_animal"],
    order_by="start_date desc")

    total_raised = sum(flt(c.amount_raised) for c in campaigns)
    total_goal = sum(flt(c.goal_amount) for c in campaigns)

    return {
        "campaigns": campaigns,
        "active_count": len(campaigns),
        "total_raised": total_raised,
        "total_goal": total_goal,
        "overall_progress": flt(total_raised / max(total_goal, 1) * 100, 1)
    }


def update_campaign_stats(campaign_name):
    """Recalculate campaign stats from linked donations."""
    campaign = frappe.get_doc("Donation Campaign", campaign_name)

    donations = frappe.get_all("Donation", filters={
        "campaign": campaign_name,
        "docstatus": ["!=", 2]
    }, fields=["amount", "donor_name"])

    total = sum(flt(d.amount) for d in donations)
    donors = len(set(d.donor_name for d in donations if d.donor_name))

    campaign.amount_raised = total
    campaign.donor_count = donors
    campaign.progress_percent = flt(total / max(flt(campaign.goal_amount), 1) * 100, 1)
    campaign.save(ignore_permissions=True)

    # Auto-complete if goal reached
    if campaign.goal_amount and total >= flt(campaign.goal_amount):
        if campaign.status == "Active":
            campaign.status = "Completed"
            campaign.save(ignore_permissions=True)

            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Donation Campaign",
                "reference_name": campaign_name,
                "content": f"🎉 Campaign goal of {campaign.goal_amount} reached! Total raised: {total}"
            }).insert(ignore_permissions=True)

    frappe.db.commit()
    return {"amount_raised": total, "donor_count": donors, "progress_percent": campaign.progress_percent}


def generate_campaign_story(campaign_name):
    """Use AI to generate a compelling campaign story."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_campaign_builder", 0):
        return {"error": "Campaign builder feature is not enabled"}

    campaign = frappe.get_doc("Donation Campaign", campaign_name)

    animal_info = ""
    if campaign.featured_animal:
        animal = frappe.get_doc("Animal", campaign.featured_animal)
        animal_info = f"""
Featured Animal: {animal.animal_name}
Species: {animal.species}, Breed: {animal.breed or 'Unknown'}
Age: {animal.estimated_age or 'Unknown'}
Story: {animal.special_notes or 'No background story yet'}
Medical: {animal.medical_status or 'Unknown'}"""

    prompt = f"""You are a nonprofit fundraising copywriter. Create a compelling campaign story:

Campaign: {campaign.campaign_name}
Type: {campaign.campaign_type}
Goal: R{flt(campaign.goal_amount):,.2f}
Current Progress: R{flt(campaign.amount_raised):,.2f} ({campaign.progress_percent or 0}%)
{animal_info}

Write:
1. A heartfelt campaign story (200-300 words) that inspires donations
2. A punchy social media post (under 280 characters)
3. An email subject line
4. 3 suggested milestone updates (25%, 50%, 75%)

Tone: Warm, hopeful, urgent but not guilt-tripping. Focus on impact."""

    from kennel_management.utils.ai_actions import call_llm
    response = call_llm(prompt)

    return {"story": response, "campaign": campaign_name}


def generate_social_media_post(campaign_name):
    """Generate a social media update for a campaign."""
    settings = frappe.get_single("Kennel Management Settings")
    if not getattr(settings, "enable_campaign_builder", 0):
        return {"error": "Campaign builder feature is not enabled"}

    campaign = frappe.get_doc("Donation Campaign", campaign_name)

    prompt = f"""Create a brief, engaging social media post for this animal shelter fundraising campaign:

Campaign: {campaign.campaign_name}
Goal: R{flt(campaign.goal_amount):,.2f}
Raised so far: R{flt(campaign.amount_raised):,.2f}
Donors: {campaign.donor_count or 0}

Write ONE social media post (max 280 characters) with:
- An emoji hook
- The key ask
- A call to action
Do not include hashtags."""

    from kennel_management.utils.ai_actions import call_llm
    response = call_llm(prompt)
    return {"post": response, "campaign": campaign_name}
