# SMS & WhatsApp Message Templates for Kennel Management
# These templates are used by the messaging utilities

SMS_TEMPLATES = {
    # Adoption Application Templates
    "adoption_received": (
        "SPCA: Thank you {applicant_name}! Your adoption application ({ref}) has been received. "
        "We will review it within 3-5 business days."
    ),
    "adoption_under_review": (
        "SPCA: Hi {applicant_name}, your adoption application ({ref}) is now under review. "
        "We may contact you or your references for more information."
    ),
    "adoption_home_check": (
        "SPCA: Hi {applicant_name}, a home check for your adoption application ({ref}) "
        "has been scheduled for {date}. Please ensure someone is home."
    ),
    "adoption_approved": (
        "SPCA: Congratulations {applicant_name}! 🎉 Your application to adopt {animal_name} ({ref}) "
        "has been APPROVED! Please visit the shelter to finalise the adoption."
    ),
    "adoption_completed": (
        "SPCA: Welcome home {animal_name}! 🏠 Congratulations {applicant_name} on your new family member. "
        "We'll check in on {followup_date}. Contact us anytime for support."
    ),
    "adoption_rejected": (
        "SPCA: Hi {applicant_name}, after careful review, your adoption application ({ref}) "
        "was not approved. Please contact us for more information."
    ),

    # Veterinary Templates
    "vet_appointment_reminder": (
        "SPCA: Reminder — Vet appointment for {animal_name} on {date} at {time}. "
        "Type: {appointment_type}. Ref: {ref}"
    ),
    "vet_appointment_completed": (
        "SPCA: Vet appointment for {animal_name} completed. "
        "Diagnosis: {diagnosis}. Follow-up: {followup_date}."
    ),

    # Lost & Found Templates
    "lost_found_received": (
        "SPCA: Your {report_type} animal report has been received (Ref: {ref}). "
        "We will check our records and contact you if there is a match."
    ),
    "lost_found_match": (
        "SPCA: Possible match found for your {report_type} report ({ref})! "
        "Please contact us as soon as possible to verify."
    ),

    # Donation Templates
    "donation_received": (
        "SPCA: Thank you {donor_name} for your generous donation of R{amount}! "
        "Receipt: {ref}. Your support makes a real difference. 🐾"
    ),

    # Foster Templates
    "foster_application_received": (
        "SPCA: Thank you {applicant_name}! Your foster application ({ref}) has been received. "
        "Our foster coordinator will contact you shortly."
    ),
    "foster_activated": (
        "SPCA: Hi {applicant_name}, your foster care for {animal_name} has been activated. "
        "Thank you for providing a temporary home! We're here to support you."
    ),

    # General Templates
    "welcome_volunteer": (
        "SPCA: Welcome {volunteer_name}! 🎉 Your volunteer application has been received. "
        "We'll contact you about orientation and next steps."
    ),
    "daily_round_alert": (
        "SPCA ALERT: {animal_name} in kennel {kennel} needs attention during {round_type} round. "
        "Reason: {reason}. Ref: {ref}"
    ),
}

WHATSAPP_TEMPLATES = {
    "adoption_approved": {
        "template_name": "adoption_approved",
        "language": "en",
        "components": [
            {
                "type": "body",
                "parameters": ["applicant_name", "animal_name", "ref"]
            }
        ]
    },
    "appointment_reminder": {
        "template_name": "vet_appointment_reminder",
        "language": "en",
        "components": [
            {
                "type": "body",
                "parameters": ["animal_name", "date", "time", "appointment_type"]
            }
        ]
    },
    "donation_thank_you": {
        "template_name": "donation_thank_you",
        "language": "en",
        "components": [
            {
                "type": "body",
                "parameters": ["donor_name", "amount"]
            }
        ]
    },
}


def get_sms_template(template_key, **kwargs):
    """Get a formatted SMS template."""
    template = SMS_TEMPLATES.get(template_key)
    if not template:
        return None
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def get_whatsapp_template(template_key):
    """Get WhatsApp template configuration."""
    return WHATSAPP_TEMPLATES.get(template_key)
