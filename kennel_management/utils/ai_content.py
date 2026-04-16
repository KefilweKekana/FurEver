"""
AI Content Generation — Social media posts, post-adoption follow-ups, RAG.

Generates compelling content for adoption promotion, donor engagement,
and retrieves shelter protocol knowledge.
"""
import frappe
from frappe.utils import today, getdate, add_days, cint, flt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SOCIAL MEDIA CONTENT GENERATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_social_media_post(animal=None, platform="general", tone="heartwarming", include_hashtags=True):
    """Generate an adoption promotion post for social media.

    Creates compelling, ready-to-post content with hashtags and call to action.
    """
    if not animal:
        return {"success": False, "error": "Please specify an animal to promote."}

    # Resolve animal
    animal_id = _resolve(animal)
    if not animal_id:
        return {"success": False, "error": f"Could not find animal: {animal}"}

    doc = frappe.get_doc("Animal", animal_id)

    # Get behavior assessment
    behavior = frappe.get_all("Behavior Assessment", filters={"animal": animal_id},
        fields=["overall_temperament", "dog_sociability", "cat_sociability",
                "child_reaction", "energy_level", "trainability_score"],
        order_by="assessment_date desc", limit=1)
    ba = behavior[0] if behavior else None

    # Build personality profile
    traits = []
    if doc.temperament:
        traits.append(doc.temperament.lower())
    if ba:
        if ba.overall_temperament:
            traits.append(ba.overall_temperament.lower())
        if ba.energy_level:
            traits.append(f"{ba.energy_level.lower()} energy")
    if doc.good_with_children == "Yes":
        traits.append("great with kids")
    if doc.good_with_dogs == "Yes":
        traits.append("dog-friendly")
    if doc.good_with_cats == "Yes":
        traits.append("cat-friendly")
    if doc.house_trained:
        traits.append("house trained")

    trait_str = ", ".join(traits[:5]) if traits else "wonderful personality"

    # Age string
    age_str = ""
    if doc.estimated_age_years:
        age_str = f"{doc.estimated_age_years} year old"
        if doc.estimated_age_months and doc.estimated_age_months > 0:
            age_str = f"{doc.estimated_age_years} and a half year old"
    elif doc.estimated_age_months:
        age_str = f"{doc.estimated_age_months} month old"
    else:
        age_str = "adorable"

    # Days in shelter
    days_in = 0
    if doc.intake_date:
        days_in = (getdate(today()) - getdate(doc.intake_date)).days

    # Build the post based on tone
    shelter_name = ""
    try:
        shelter_name = frappe.db.get_single_value("Kennel Management Settings", "shelter_name") or "our shelter"
    except Exception:
        shelter_name = "our shelter"

    species_lower = (doc.species or "animal").lower()
    breed_str = doc.breed or species_lower

    if tone == "heartwarming":
        post = _heartwarming_post(doc, age_str, breed_str, trait_str, days_in, shelter_name, species_lower)
    elif tone == "urgent":
        post = _urgent_post(doc, age_str, breed_str, trait_str, days_in, shelter_name, species_lower)
    elif tone == "fun":
        post = _fun_post(doc, age_str, breed_str, trait_str, days_in, shelter_name, species_lower)
    else:
        post = _professional_post(doc, age_str, breed_str, trait_str, days_in, shelter_name, species_lower)

    # Platform-specific adjustments
    if platform == "twitter":
        # Trim to ~250 chars for X/Twitter
        if len(post) > 250:
            post = post[:247] + "..."

    # Hashtags
    hashtags = ""
    if include_hashtags:
        base_tags = ["#AdoptDontShop", "#RescuePet", "#ShelterAnimal", "#ForeverHome"]
        species_tags = {
            "Dog": ["#RescueDog", "#AdoptADog", "#DogsOfSA"],
            "Cat": ["#RescueCat", "#AdoptACat", "#CatsOfSA"],
        }
        breed_tags = [f"#{doc.breed.replace(' ', '')}" if doc.breed else ""]
        name_tag = f"#{doc.animal_name.replace(' ', '')}" if doc.animal_name else ""

        all_tags = base_tags + species_tags.get(doc.species, []) + breed_tags + [name_tag]
        all_tags = [t for t in all_tags if t and t != "#"]

        if platform == "instagram":
            all_tags += ["#PetsOfInstagram", "#AnimalRescue", "#ShelterPetsOfInstagram",
                        "#AdoptMe", "#SaveALife", f"#{shelter_name.replace(' ', '')}"]
        elif platform == "facebook":
            all_tags = all_tags[:6]  # Facebook doesn't need many

        hashtags = "\n\n" + " ".join(all_tags[:12])

    full_post = post + hashtags

    return {
        "success": True,
        "post": full_post,
        "platform": platform,
        "animal_name": doc.animal_name,
        "character_count": len(full_post),
        "message": f"**Social media post for {doc.animal_name}** ({platform}):\n\n---\n{full_post}\n---\n\nReady to copy and post! ({len(full_post)} characters)",
    }


def _heartwarming_post(doc, age_str, breed_str, traits, days_in, shelter, species):
    name = doc.animal_name
    if days_in > 30:
        waiting = f"\n\n{name} has been waiting {days_in} days for a family to call their own. Could you be the one?"
    else:
        waiting = f"\n\nCome meet {name} and fall in love!"

    return (
        f"Meet {name} 💛\n\n"
        f"This {age_str} {breed_str} is looking for their forever home! "
        f"{name} is {traits} and ready to fill your life with love and joy.\n"
        f"{waiting}\n\n"
        f"📍 Visit {shelter}\n"
        f"📞 Contact us to arrange a meet-and-greet\n"
        f"🐾 Adoption includes vaccinations, microchip & sterilisation"
    )


def _urgent_post(doc, age_str, breed_str, traits, days_in, shelter, species):
    name = doc.animal_name
    return (
        f"⚠️ URGENT: {name} NEEDS A HOME ⚠️\n\n"
        f"This beautiful {age_str} {breed_str} has been at {shelter} for {days_in} days "
        f"and is still waiting for someone to give them a chance.\n\n"
        f"{name} is {traits}. All they need is someone to believe in them.\n\n"
        f"Every share helps. Every visit counts. Could you be {name}'s miracle?\n\n"
        f"📍 {shelter}\n"
        f"📞 Contact us TODAY — {name} is waiting"
    )


def _fun_post(doc, age_str, breed_str, traits, days_in, shelter, species):
    name = doc.animal_name
    emoji = "🐕" if species == "dog" else "🐱" if species == "cat" else "🐾"

    return (
        f"{emoji} Hi, I'm {name}! {emoji}\n\n"
        f"I'm a {age_str} {breed_str} with a {traits} personality! "
        f"My hobbies include being adorable, getting belly rubs, and looking at you with my best puppy eyes.\n\n"
        f"I've been practising my 'take me home' face and I think I've got it down pretty well! "
        f"Come see for yourself at {shelter}.\n\n"
        f"Warning: Side effects of meeting me may include uncontrollable smiling "
        f"and a sudden urge to adopt. 😊"
    )


def _professional_post(doc, age_str, breed_str, traits, days_in, shelter, species):
    name = doc.animal_name
    details = []
    if doc.species: details.append(f"Species: {doc.species}")
    if doc.breed: details.append(f"Breed: {doc.breed}")
    if age_str: details.append(f"Age: {age_str}")
    if doc.gender: details.append(f"Gender: {doc.gender}")
    if doc.size: details.append(f"Size: {doc.size}")
    if doc.spay_neuter_status: details.append(f"Sterilised: {'Yes' if doc.spay_neuter_status != 'Intact' else 'No'}")
    compatibility = []
    if doc.good_with_children == "Yes": compatibility.append("children")
    if doc.good_with_dogs == "Yes": compatibility.append("dogs")
    if doc.good_with_cats == "Yes": compatibility.append("cats")

    return (
        f"🐾 Adoption Feature: {name}\n\n"
        f"{' | '.join(details)}\n\n"
        f"Temperament: {traits}\n"
        + (f"Compatible with: {', '.join(compatibility)}\n" if compatibility else "")
        + f"\n{name} is available for adoption at {shelter}. "
        f"All adoptions include vaccinations, microchipping, and sterilisation.\n\n"
        f"Contact us to schedule a meet-and-greet."
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST-ADOPTION FOLLOW-UP SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_followup_messages():
    """Generate personalized post-adoption follow-up messages.

    Called by scheduled task. Creates follow-ups at 1 week, 1 month, 3 months.
    """
    now = today()
    followup_schedule = [
        (7, "one_week", "1 Week"),
        (30, "one_month", "1 Month"),
        (90, "three_months", "3 Months"),
    ]

    messages_created = 0

    for days, tag, label in followup_schedule:
        target_date = add_days(now, -days)

        # Find adoptions completed on that date
        adoptions = frappe.get_all("Adoption Application",
            filters={
                "status": "Adoption Completed",
                "adoption_date": target_date,
            },
            fields=["name", "applicant_name", "email", "phone", "animal_name", "animal",
                    "species_preference"],
        )

        for adoption in adoptions:
            # Check if follow-up already sent for this tag
            existing = frappe.db.exists("Communication", {
                "reference_doctype": "Adoption Application",
                "reference_name": adoption.name,
                "subject": ["like", f"%{label} Follow-Up%"],
            })
            if existing:
                continue

            # Get animal details for personalization
            animal_doc = None
            if adoption.animal and frappe.db.exists("Animal", adoption.animal):
                animal_doc = frappe.get_doc("Animal", adoption.animal)

            message = _build_followup_message(adoption, animal_doc, days, label)

            if adoption.email:
                try:
                    settings = frappe.get_single("Kennel Management Settings")
                    shelter_name = settings.shelter_name or "SPCA"

                    frappe.sendmail(
                        recipients=[adoption.email],
                        subject=f"{label} Follow-Up: How is {adoption.animal_name or 'your new pet'} doing? 🐾",
                        message=message,
                        reference_doctype="Adoption Application",
                        reference_name=adoption.name,
                    )
                    messages_created += 1
                except Exception:
                    frappe.log_error(frappe.get_traceback(), "Post-Adoption Follow-up Error")

    return messages_created


def _build_followup_message(adoption, animal_doc, days, label):
    """Build a personalized follow-up email."""
    from frappe.utils import escape_html
    name = escape_html(adoption.applicant_name or "there")
    animal_name = escape_html(adoption.animal_name or "your new pet")
    first_name = name.split()[0] if name else "there"

    # Get breed-specific tips
    breed_tips = ""
    if animal_doc:
        breed_tips = _get_breed_tips(animal_doc)

    try:
        shelter_name = frappe.db.get_single_value("Kennel Management Settings", "shelter_name") or "SPCA"
    except Exception:
        shelter_name = "SPCA"

    if days == 7:
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #7c3aed;">Hi {first_name}! 🐾</h2>
            <p>It's been one week since {animal_name} joined your family, and we'd love to hear how things are going!</p>
            <p>The first week can be an adjustment period for both of you. Here are some things that are completely normal:</p>
            <ul>
                <li>Hiding or being shy — {animal_name} is still learning their new environment</li>
                <li>Changes in appetite — stress from the move can affect eating</li>
                <li>Accidents in the house — it takes time to learn a new routine</li>
                <li>Testing boundaries — {animal_name} is figuring out the rules</li>
            </ul>
            {breed_tips}
            <p><strong>Quick checklist:</strong></p>
            <ul>
                <li>✅ Set up a vet appointment for a wellness check within the first 2 weeks</li>
                <li>✅ Establish a consistent feeding and walking routine</li>
                <li>✅ Create a safe space where {animal_name} can retreat when overwhelmed</li>
                <li>✅ Update microchip registration with your details</li>
            </ul>
            <p>If you have any concerns, please don't hesitate to contact us — we're always here to help!</p>
            <p>Warm regards,<br>The {shelter_name} Team</p>
            <p style="color: #666; font-size: 12px;">We'd love to see photos of {animal_name} in their new home! Reply to this email with updates. 📸</p>
        </div>
        """
    elif days == 30:
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #7c3aed;">One Month Update — How is {animal_name}? 🎉</h2>
            <p>Hi {first_name},</p>
            <p>Can you believe it's been a month already? By now, {animal_name} should be settling into their routine and really starting to show their true personality.</p>
            <p>At the one-month mark, most pets:</p>
            <ul>
                <li>Feel more confident and relaxed in their environment</li>
                <li>Have established a daily routine with you</li>
                <li>Are bonding more deeply with family members</li>
                <li>May start showing playful behaviors they were too stressed to show before</li>
            </ul>
            {breed_tips}
            <p><strong>Monthly reminders:</strong></p>
            <ul>
                <li>🏥 Complete first vet visit if not done yet</li>
                <li>💊 Keep up with flea/tick and deworming schedule</li>
                <li>🎾 Regular exercise and mental stimulation</li>
                <li>❤️ Socialization with other animals (if compatible)</li>
            </ul>
            <p>We love hearing success stories — feel free to share photos and updates with us!</p>
            <p>With love,<br>The {shelter_name} Team</p>
        </div>
        """
    else:  # 90 days
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #7c3aed;">3 Months Together! 🐾💛</h2>
            <p>Hi {first_name},</p>
            <p>Three months! {animal_name} is a true family member by now, and we couldn't be happier about this match.</p>
            <p>By the 3-month mark, the "3-3-3 rule" is complete:</p>
            <ul>
                <li><strong>3 days:</strong> Decompressing from shelter life ✅</li>
                <li><strong>3 weeks:</strong> Learning your routine ✅</li>
                <li><strong>3 months:</strong> Feeling completely at home ✅</li>
            </ul>
            <p>{animal_name} should now be showing you their full, authentic personality — and we hope it's as wonderful as we always knew it would be!</p>
            <p><strong>Long-term care reminders:</strong></p>
            <ul>
                <li>📅 Annual vet check-up due in {12 - 3} months</li>
                <li>💉 Keep vaccination schedule up to date</li>
                <li>🦷 Consider dental cleaning if needed</li>
                <li>⚖️ Monitor weight — adjust food as needed</li>
            </ul>
            <p>If you'd like to help other animals find their forever homes, consider:</p>
            <ul>
                <li>🌟 Leaving a review about your adoption experience</li>
                <li>📣 Sharing our available animals on social media</li>
                <li>💰 A small donation to help animals still waiting</li>
                <li>🏠 Becoming a foster parent</li>
            </ul>
            <p>Thank you for giving {animal_name} a second chance. You changed a life.</p>
            <p>Forever grateful,<br>The {shelter_name} Team</p>
        </div>
        """


def _get_breed_tips(animal_doc):
    """Get breed-specific care tips."""
    species = animal_doc.species or ""
    breed = (animal_doc.breed or "").lower()

    tips = ""
    if species == "Dog":
        if any(b in breed for b in ["labrador", "retriever", "golden"]):
            tips = "<p><strong>Breed tip:</strong> Labradors and Retrievers are prone to weight gain — monitor portions and ensure daily exercise! They also love swimming and fetching.</p>"
        elif any(b in breed for b in ["german shepherd", "gsd", "alsatian"]):
            tips = "<p><strong>Breed tip:</strong> German Shepherds are highly intelligent and need mental stimulation. Consider puzzle toys and training sessions. Watch for hip dysplasia as they age.</p>"
        elif any(b in breed for b in ["pitbull", "pit bull", "staffy", "staffordshire"]):
            tips = "<p><strong>Breed tip:</strong> Staffies are incredibly loyal and affectionate! They thrive on human companionship and can be sensitive to cold weather. Regular exercise and positive reinforcement training work best.</p>"
        elif any(b in breed for b in ["husky", "malamute"]):
            tips = "<p><strong>Breed tip:</strong> Huskies need lots of exercise and mental stimulation. They're escape artists — check your fencing! They shed heavily twice a year.</p>"
        elif any(b in breed for b in ["dachshund", "sausage"]):
            tips = "<p><strong>Breed tip:</strong> Dachshunds are prone to back problems — avoid jumping from heights and support their back when carrying them. They're stubborn but food-motivated!</p>"
        elif "mix" in breed or "cross" in breed:
            tips = "<p><strong>Mixed breed bonus:</strong> Mixed breeds often enjoy hybrid vigour — fewer breed-specific health issues. Every mixed breed is unique and special!</p>"
    elif species == "Cat":
        if any(b in breed for b in ["siamese"]):
            tips = "<p><strong>Breed tip:</strong> Siamese cats are very vocal and social — they'll 'talk' to you! They need companionship and don't do well when left alone for long periods.</p>"
        elif any(b in breed for b in ["persian"]):
            tips = "<p><strong>Breed tip:</strong> Persians need daily grooming to prevent matting. Watch for eye discharge and keep their face clean. They prefer calm environments.</p>"

    return tips


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RAG — SHELTER PROTOCOL RETRIEVAL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Built-in protocol knowledge base (no vector DB needed — embedded in-app)
SHELTER_PROTOCOLS = {
    "quarantine": {
        "title": "Quarantine Protocol",
        "content": """
**Quarantine Protocol**
1. ALL new admissions go through minimum 7-day quarantine (10 days recommended)
2. Quarantine kennels must be separate from general population
3. Staff must wear PPE (gloves, gown) when entering quarantine
4. Separate cleaning equipment for quarantine area
5. Monitor for: respiratory illness, diarrhea, vomiting, nasal/eye discharge, coughing, sneezing
6. Temperature check daily
7. No contact with other animals during quarantine
8. Quarantine can be extended if symptoms develop
9. Vet exam required before release from quarantine
10. Disinfect kennel with veterinary-grade disinfectant between occupants
""",
        "keywords": ["quarantine", "isolation", "new arrival", "new animal", "intake", "contagious", "disease", "sick", "ppe"],
    },
    "parvo": {
        "title": "Parvovirus Protocol",
        "content": """
**Parvovirus (Parvo) Protocol**
- EMERGENCY — highly contagious and potentially fatal, especially in puppies
- Symptoms: severe bloody diarrhea, vomiting, lethargy, loss of appetite, dehydration
- IMMEDIATELY isolate suspected cases (separate from quarantine and general pop)
- Notify veterinarian immediately
- Use diluted bleach (1:30) for disinfection — parvo is resistant to most disinfectants
- Staff must change PPE between parvo cases and other animals
- Incubation period: 3-7 days
- Treatment: IV fluids, anti-nausea meds, antibiotics for secondary infections
- Survival rate with treatment: 68-92%
- Vaccination is the best prevention — ensure all puppies receive DHPP series
- Contaminated areas remain infectious for up to 1 year outdoors
""",
        "keywords": ["parvo", "parvovirus", "bloody diarrhea", "puppy", "vomiting", "contagious", "bleach"],
    },
    "kennel_cough": {
        "title": "Kennel Cough Protocol",
        "content": """
**Kennel Cough (Canine Infectious Respiratory Disease) Protocol**
- Highly contagious respiratory infection
- Symptoms: persistent dry honking cough, sneezing, nasal discharge, mild fever
- Isolate affected dogs immediately
- Usually self-limiting (1-3 weeks) but can progress to pneumonia
- Treatment: rest, humidifier, cough suppressant (vet-prescribed), antibiotics if secondary infection
- Bordetella vaccination recommended for all dogs in shelter
- Ventilation is key — ensure good airflow in kennel areas
- Can spread through airborne droplets, contaminated surfaces, and direct contact
""",
        "keywords": ["kennel cough", "cough", "coughing", "respiratory", "bordetella", "sneezing", "honking"],
    },
    "bite_protocol": {
        "title": "Bite Incident Protocol",
        "content": """
**Bite Incident Protocol**
1. SAFETY FIRST — secure the animal, ensure no further risk
2. Provide first aid to the person bitten (wash wound, apply antiseptic)
3. Seek medical attention for any bite that breaks skin
4. Document the incident: who, when, where, witnesses, severity, circumstances
5. Photograph injuries
6. Place animal on behavior hold pending assessment
7. Notify management/supervisor immediately
8. 10-day rabies observation period (if rabies status unknown)
9. Complete incident report form within 24 hours
10. Behavior assessment required before animal can be returned to general population
11. Consider if bite was provoked (food guarding, pain, fear) vs. unprovoked
12. Report to local animal control if required by law
""",
        "keywords": ["bite", "bitten", "attack", "aggressive", "injury", "rabies", "observation", "incident"],
    },
    "euthanasia": {
        "title": "Euthanasia Decision Protocol",
        "content": """
**Euthanasia Decision Protocol**
- Euthanasia is a last resort, considered only when:
  1. Untreatable suffering (terminal illness, severe chronic pain)
  2. Dangerous aggression that cannot be safely managed (multiple unprovoked bite incidents)
  3. Severe behavioral issues unresponsive to treatment
  4. Quality of life assessment indicates ongoing suffering
- Decision must be approved by: shelter manager AND attending veterinarian
- Independent behavior assessment required for aggression cases
- Explore all alternatives first: transfer to breed-specific rescue, sanctuary, behavioral rehabilitation
- Owner surrender agreements may include return-before-euthanasia clauses
- Procedure performed by licensed veterinarian only
- Two-person verification of identity before procedure
- Handle remains with dignity according to shelter policy
""",
        "keywords": ["euthanasia", "put down", "put to sleep", "end of life", "quality of life", "suffering", "aggressive"],
    },
    "adoption_process": {
        "title": "Adoption Process SOP",
        "content": """
**Standard Adoption Process**
1. **Application**: Adopter completes application (online or in-person)
2. **Review**: Staff reviews application within 48 hours
3. **Home Check**: Scheduled for shortlisted applicants (verify housing, yard, fencing)
4. **Meet & Greet**: Applicant meets animal, observe interaction
5. **Compatibility Check**: If existing pets, arrange supervised introduction
6. **Approval**: Manager reviews and approves/rejects
7. **Contract**: Adopter signs adoption contract (includes sterilisation clause)
8. **Fee Payment**: Collect adoption fee (includes vaccinations, microchip, sterilisation)
9. **Handover**: Brief adopter on animal's needs, medical history, feeding schedule
10. **Follow-up**: Automated check-ins at 1 week, 1 month, 3 months
11. **Return Policy**: Animals can be returned within 30 days if not working out
""",
        "keywords": ["adoption", "adopt", "process", "application", "home check", "meet and greet", "contract", "fee"],
    },
    "intake_triage": {
        "title": "Intake Triage Protocol",
        "content": """
**Intake Triage Protocol**
Priority levels:
- **EMERGENCY** (immediate vet): Active bleeding, difficulty breathing, unconscious, seizures, open fractures, poisoning
- **URGENT** (vet within 2 hours): Severe dehydration, suspected broken bones, large wounds, extreme lethargy, prolapsed organs
- **HIGH** (vet within 24 hours): Limping, eye injuries, skin infections, mild dehydration, diarrhea/vomiting
- **STANDARD** (routine processing): Healthy, minor issues, preventive care needed

Steps:
1. Quick visual assessment (30 seconds) — identify emergencies
2. Temperament check — is animal safe to handle?
3. Body condition score (1-9 scale)
4. Check for identification (microchip scan, collar, tags)
5. Photograph from multiple angles
6. Weight and basic measurements
7. Assign triage priority
8. Assign to appropriate kennel (quarantine for all new arrivals)
9. Create admission record
10. Schedule intake exam with vet
""",
        "keywords": ["intake", "triage", "arrival", "new animal", "emergency", "assessment", "priority", "body condition"],
    },
    "cleaning": {
        "title": "Kennel Cleaning Protocol",
        "content": """
**Daily Kennel Cleaning Protocol**
1. Remove animal to temporary holding area
2. Remove all bedding, food bowls, water bowls, toys
3. Dry-clean: sweep/scoop solid waste
4. Pre-rinse with water
5. Apply veterinary-grade disinfectant (follow dilution instructions)
6. Allow 10-minute contact time (CRITICAL — don't rinse too early)
7. Rinse thoroughly — residue can irritate paws and skin
8. Squeegee and allow to dry
9. Replace clean bedding, fresh food and water
10. Return animal
11. Log cleaning in daily rounds

Between occupants (deep clean):
- Same as above PLUS pressure wash walls and floor
- Replace all consumables (bowls, toys if not disinfectable)
- Allow 24-hour drying period if possible

Isolation/Quarantine areas:
- Dedicated cleaning equipment (colour-coded)
- Clean LAST to prevent cross-contamination
- Double disinfection cycle
- PPE required: gloves, gown, shoe covers
""",
        "keywords": ["cleaning", "clean", "disinfect", "sanitize", "hygiene", "kennel maintenance", "bleach", "disinfectant"],
    },
    "feeding": {
        "title": "Feeding Protocol",
        "content": """
**Feeding Protocol**
Schedule:
- Morning feed: 7:00 AM
- Afternoon feed: 3:00 PM
- Puppies/kittens under 6 months: 3 feeds per day (add midday feed at 11:00 AM)

Guidelines:
- Fresh water must be available at all times (check twice daily)
- Feed according to weight and age (see feeding chart on kennel card)
- Monitor appetite — loss of appetite is often first sign of illness
- Record any animal that doesn't eat on daily round report
- Separate food-aggressive animals during feeding
- Medication can be hidden in food (coordinate with vet team)
- Special diets: check kennel card for prescription diets
- Clean bowls after every meal
- Store food in sealed containers, check expiry dates
- Overdue alert: if feeding round not complete within 60 minutes, notify supervisor
""",
        "keywords": ["feeding", "feed", "food", "diet", "appetite", "water", "nutrition", "hungry", "eating"],
    },
    "lost_animal": {
        "title": "Lost Animal Report Protocol",
        "content": """
**Lost Animal Report Protocol**
When someone reports a lost pet:
1. Complete Lost and Found Report form with full details
2. Get description: species, breed, color, markings, size, age, gender, name
3. Get last seen: location, date, time, circumstances
4. Get owner info: name, phone, email, address
5. Check for microchip number (owner may have records)
6. Ask for recent photos
7. Cross-reference against current shelter animals and recent intakes
8. Check against existing Found reports
9. Advise owner to:
   - Check with neighbours and local vets
   - Post on social media and community groups
   - Put up flyers in last-seen area
   - Check shelter website regularly
   - Visit shelter in person (photos don't always match)
10. Keep report open for 90 days, then follow up before closing
""",
        "keywords": ["lost", "missing", "found", "stray", "reunite", "owner", "microchip", "report"],
    },
}


def search_protocols(query):
    """Search shelter protocols using keyword matching.

    This is a lightweight RAG implementation that doesn't require external
    vector databases — protocols are embedded directly in the application.
    """
    if not query:
        return {"success": True, "results": list(SHELTER_PROTOCOLS.keys()),
                "message": "Available protocols: " + ", ".join(SHELTER_PROTOCOLS.keys())}

    query_lower = query.lower()
    query_words = set(query_lower.split())

    # Score each protocol
    scored = []
    for key, protocol in SHELTER_PROTOCOLS.items():
        score = 0

        # Keyword matching
        for kw in protocol["keywords"]:
            if kw in query_lower:
                score += 10
            for word in query_words:
                if word in kw:
                    score += 3

        # Title matching
        if any(word in protocol["title"].lower() for word in query_words):
            score += 8

        # Content matching
        content_lower = protocol["content"].lower()
        for word in query_words:
            if len(word) > 3 and word in content_lower:
                score += 2

        if score > 0:
            scored.append({"key": key, "title": protocol["title"],
                          "content": protocol["content"], "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:3]

    if top_results:
        msg = "**Relevant Protocols:**\n\n"
        for r in top_results:
            msg += r["content"] + "\n\n"
        return {"success": True, "results": top_results, "message": msg}
    else:
        return {"success": True, "results": [],
                "message": "No matching protocols found. Available topics: " +
                    ", ".join(SHELTER_PROTOCOLS.keys())}


def get_protocol_context_for_ai():
    """Get a condensed version of all protocols for inclusion in AI context."""
    lines = ["Available shelter protocols (user can ask about any):"]
    for key, protocol in SHELTER_PROTOCOLS.items():
        lines.append(f"  • {protocol['title']} — keywords: {', '.join(protocol['keywords'][:5])}")
    return "\n".join(lines)


def _resolve(identifier):
    """Resolve animal identifier."""
    if not identifier:
        return None
    if frappe.db.exists("Animal", identifier):
        return identifier
    matches = frappe.get_all("Animal", filters={"animal_name": ["like", f"%{identifier}%"]},
        fields=["name"], order_by="creation desc", limit=1)
    return matches[0].name if matches else None
