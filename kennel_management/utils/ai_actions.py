"""
AI Agent Actions — Function Calling System for Scout.

Defines tools that the AI can invoke to CREATE, UPDATE, and MANAGE shelter records
through natural language. This is the backbone of Scout's "do things" capability.
"""
import frappe
from frappe import _
from frappe.utils import today, getdate, add_days, now_datetime, cint, flt
import json


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL DEFINITIONS (OpenAI-compatible function calling schema)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCOUT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_animal_admission",
            "description": "Create a new animal admission record to intake an animal into the shelter. Use when staff says things like 'admit a new dog', 'we have a stray cat', 'intake this animal'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal_name": {"type": "string", "description": "Name of the animal (e.g. 'Buddy', 'Unknown Stray')"},
                    "species": {"type": "string", "enum": ["Dog", "Cat", "Bird", "Rabbit", "Reptile", "Small Animal", "Farm Animal", "Other"]},
                    "breed": {"type": "string", "description": "Breed of the animal (e.g. 'Labrador', 'Domestic Shorthair')"},
                    "gender": {"type": "string", "enum": ["Male", "Female", "Unknown"]},
                    "estimated_age": {"type": "string", "description": "Estimated age (e.g. '2 years', '6 months', 'puppy')"},
                    "color": {"type": "string", "description": "Color/markings (e.g. 'black and white', 'tan')"},
                    "weight_kg": {"type": "number", "description": "Weight in kilograms"},
                    "admission_type": {"type": "string", "enum": ["Stray", "Owner Surrender", "Rescue", "Transfer In", "Born in Shelter", "Confiscation", "Return from Adoption", "Return from Foster"]},
                    "condition_on_arrival": {"type": "string", "enum": ["Excellent", "Good", "Fair", "Poor", "Critical"]},
                    "requires_quarantine": {"type": "boolean", "description": "Whether the animal needs quarantine"},
                    "notes": {"type": "string", "description": "Any additional intake notes"},
                    "surrenderer_name": {"type": "string", "description": "Name of person surrendering (for Owner Surrender)"},
                    "surrenderer_phone": {"type": "string", "description": "Phone of person surrendering"},
                },
                "required": ["animal_name", "species", "admission_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_animal_status",
            "description": "Update an animal's status. Use when staff says 'mark Bella as adopted', 'put Rex in quarantine', 'Daisy is available for adoption now'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Animal ID (KM-ANM-XXXX-XXXXX) or animal name"},
                    "new_status": {"type": "string", "enum": ["Available for Adoption", "Adopted", "In Foster Care", "Medical Hold", "Behavior Hold", "Quarantine", "Stray Hold", "In Treatment", "Reserved", "Transferred", "Deceased", "Returned to Owner", "Lost in Care"]},
                    "reason": {"type": "string", "description": "Reason for status change"},
                },
                "required": ["animal", "new_status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_vet_appointment",
            "description": "Schedule a veterinary appointment for an animal. Use when staff says 'book a vet check for Buddy', 'schedule spay for Bella tomorrow'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Animal ID or name"},
                    "appointment_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "appointment_time": {"type": "string", "description": "Time in HH:MM format (24hr)"},
                    "appointment_type": {"type": "string", "enum": ["Intake Exam", "Wellness Check", "Vaccination", "Spay-Neuter", "Surgery", "Dental", "Emergency", "Follow-up", "Lab Work", "X-Ray", "Microchipping", "Deworming", "Flea Treatment", "Behavioral Consult", "Euthanasia Evaluation", "Other"]},
                    "priority": {"type": "string", "enum": ["Routine", "Urgent", "Emergency"]},
                    "notes": {"type": "string", "description": "Additional notes for the vet"},
                    "veterinarian": {"type": "string", "description": "Veterinarian email/user ID"},
                },
                "required": ["animal", "appointment_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assign_kennel",
            "description": "Assign an animal to a specific kennel or find the best available kennel. Use when staff says 'move Buddy to kennel A3', 'find a kennel for the new cat'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Animal ID or name"},
                    "kennel": {"type": "string", "description": "Specific kennel name (e.g. 'A3', 'Dog Kennel 5'). Leave empty for auto-assignment."},
                    "requires_quarantine": {"type": "boolean", "description": "Whether to assign a quarantine kennel"},
                    "requires_isolation": {"type": "boolean", "description": "Whether to assign an isolation kennel"},
                },
                "required": ["animal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_adoption_application",
            "description": "Update the status of an adoption application. Use when staff says 'approve the Martinez application', 'schedule home check for APP-001'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "application": {"type": "string", "description": "Application ID (KM-ADP-XXXX-XXXXX) or applicant name"},
                    "new_status": {"type": "string", "enum": ["Pending", "Under Review", "Home Check Scheduled", "Home Check Completed", "Approved", "Rejected", "Adoption Completed", "Withdrawn", "Waitlisted"]},
                    "notes": {"type": "string", "description": "Notes about the status change"},
                    "animal": {"type": "string", "description": "Animal to assign to this application (if approving/completing)"},
                },
                "required": ["application", "new_status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_veterinary_record",
            "description": "Create a veterinary record for an animal. Use when staff says 'log Buddy's exam results', 'record that Bella got her rabies vaccine'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Animal ID or name"},
                    "record_type": {"type": "string", "enum": ["Examination", "Vaccination", "Surgery", "Treatment", "Lab Results", "Dental", "Emergency", "Behavior", "Other"]},
                    "description": {"type": "string", "description": "Description of the examination/procedure"},
                    "treatment": {"type": "string", "description": "Treatment given"},
                    "veterinarian": {"type": "string", "description": "Vet user ID"},
                    "vaccinations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "vaccine_name": {"type": "string"},
                                "next_due_date": {"type": "string", "description": "YYYY-MM-DD"}
                            }
                        },
                        "description": "Vaccinations administered"
                    },
                    "medications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "medication_name": {"type": "string"},
                                "dosage": {"type": "string"},
                                "frequency": {"type": "string"},
                                "start_date": {"type": "string"},
                                "end_date": {"type": "string"}
                            }
                        },
                        "description": "Medications prescribed"
                    },
                },
                "required": ["animal", "record_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_lost_and_found_report",
            "description": "Create a lost or found animal report. Use when someone reports a lost pet or a found stray.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_type": {"type": "string", "enum": ["Lost", "Found", "Sighted"]},
                    "reporter_name": {"type": "string"},
                    "reporter_phone": {"type": "string"},
                    "reporter_email": {"type": "string"},
                    "species": {"type": "string"},
                    "breed": {"type": "string"},
                    "color": {"type": "string"},
                    "gender": {"type": "string", "enum": ["Male", "Female", "Unknown"]},
                    "last_seen_location": {"type": "string"},
                    "last_seen_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "description": {"type": "string", "description": "Detailed description of the animal"},
                    "microchip_number": {"type": "string"},
                },
                "required": ["report_type", "species"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_adoption_matches",
            "description": "Run the AI adoption matching engine to find the best animal-applicant matches. Use when staff asks 'who should adopt Bella?', 'find matches for the pending applications', 'which animals suit the Martinez family?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Specific animal to find matches for (ID or name). Leave empty to match all available animals."},
                    "applicant": {"type": "string", "description": "Specific applicant to find matches for (ID or name). Leave empty to check all pending applicants."},
                    "top_n": {"type": "integer", "description": "Number of top matches to return", "default": 5},
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_lost_found_matching",
            "description": "Run AI matching to find potential matches between lost reports and shelter animals or found reports. Use when staff asks 'check if any shelter animals match this lost report', 'could this stray be someone's lost pet?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report": {"type": "string", "description": "Lost and Found Report ID to match against. Leave empty to check all open reports."},
                    "animal": {"type": "string", "description": "Specific animal to check against lost reports."},
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_social_media_post",
            "description": "Generate an adoption promotion post for social media (Facebook/Instagram). Use when staff says 'write a post for Bella', 'create an adoption ad', 'promote our long-stay animals'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Animal ID or name to promote"},
                    "platform": {"type": "string", "enum": ["facebook", "instagram", "twitter", "general"], "description": "Target platform"},
                    "tone": {"type": "string", "enum": ["heartwarming", "urgent", "fun", "professional"], "description": "Tone of the post"},
                    "include_hashtags": {"type": "boolean", "description": "Whether to include hashtags", "default": True},
                },
                "required": ["animal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_smart_kennel_recommendation",
            "description": "Get AI-powered kennel placement recommendation for an animal based on temperament, compatibility, medical needs, and current occupancy. Use when staff asks 'where should we put this new dog?', 'best kennel for a fearful cat?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Animal ID or name"},
                    "species": {"type": "string", "description": "Species (if animal not yet in system)"},
                    "temperament": {"type": "string", "description": "Temperament (if animal not yet in system)"},
                    "requires_quarantine": {"type": "boolean"},
                    "requires_isolation": {"type": "boolean"},
                    "is_special_needs": {"type": "boolean"},
                    "size": {"type": "string", "enum": ["Tiny", "Small", "Medium", "Large", "Giant"]},
                    "good_with_dogs": {"type": "string", "enum": ["Yes", "No", "Unknown"]},
                    "good_with_cats": {"type": "string", "enum": ["Yes", "No", "Unknown"]},
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_health_predictions",
            "description": "Get AI health predictions and risk analysis for an animal or the whole shelter. Use when staff asks 'any health concerns for Buddy?', 'which animals are at risk?', 'health trends this month'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Specific animal ID or name. Leave empty for shelter-wide analysis."},
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_donor_insights",
            "description": "Get donor intelligence - donation trends, lapsed donors, campaign analysis, suggested re-engagement. Use when staff asks about donations, fundraising, donor patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "analysis_type": {"type": "string", "enum": ["overview", "trends", "lapsed_donors", "top_donors", "campaign_analysis"], "description": "Type of donor analysis"},
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_donation",
            "description": "Record a new donation. Use when staff says 'log a R500 donation from John Smith', 'we received supplies from PetCo'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "donor_name": {"type": "string"},
                    "amount": {"type": "number"},
                    "donation_type": {"type": "string", "enum": ["Monetary", "Supplies", "Services", "Sponsorship", "Legacy"]},
                    "payment_method": {"type": "string", "enum": ["Cash", "EFT", "Card", "Online", "Cheque", "Other"]},
                    "notes": {"type": "string"},
                },
                "required": ["donor_name", "amount"]
            }
        }
    },
    # ── New Feature Tools ───────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_adoption_score",
            "description": "Get a predictive adoption score for an animal — likelihood of adoption, estimated days, and promotion recommendations. Use when staff asks 'how adoptable is Bella?', 'which animals need help?', 'adoption score for Rex'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal": {"type": "string", "description": "Animal ID or name. Leave empty for all available animals ranked by need."},
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_volunteer_schedule",
            "description": "Get smart volunteer scheduling suggestions for today — matches volunteers to shelter needs based on skills and availability. Use when staff asks 'who can help today?', 'volunteer schedule', 'need someone to walk dogs'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_volunteer_engagement",
            "description": "Get volunteer engagement analytics — top volunteers, low engagement, skill inventory. Use when staff asks 'how are volunteers doing?', 'volunteer stats', 'who hasn't volunteered lately?'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_platform_listing",
            "description": "Generate PetFinder/Adopt-a-Pet listings for available animals. Creates adoption platform-ready data with engaging descriptions. Use when staff asks 'update petfinder', 'generate adoption listings', 'sync to petfinder'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_capacity_forecast",
            "description": "Get shelter capacity forecast with occupancy predictions and recommendations. Use when asked 'capacity forecast', 'how full will we be?', 'are we running out of space?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Number of days to forecast (default 14)", "default": 14}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_status",
            "description": "Check shelter supply inventory levels, low stock alerts, and consumption rates. Use when asked 'inventory check', 'what supplies do we need?', 'stock levels'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_training_progress",
            "description": "Get training progress and adoption readiness for an animal or all animals. Use when asked 'training progress', 'is Buddy ready for adoption?', 'who needs training?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal_name": {"type": "string", "description": "Animal ID or name (optional — omit for overview)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_medical_timeline",
            "description": "Get full medical history timeline for an animal including vet visits, vaccinations, medications, and behavior assessments. Use when asked 'medical history for Rex', 'what treatments has Bella had?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal_name": {"type": "string", "description": "Animal ID or name"}
                },
                "required": ["animal_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_lost_pet_alert",
            "description": "Send community alert for a lost pet report to all volunteers and community contacts. Use when asked 'send lost pet alert', 'notify community about lost dog'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_name": {"type": "string", "description": "Lost and Found Report ID"}
                },
                "required": ["report_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_dashboard",
            "description": "Get donation campaign dashboard with all active campaigns, progress, and totals. Use when asked 'campaign status', 'how are donations?', 'fundraising progress'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_enrichment_summary",
            "description": "Get enrichment activity summary for animals showing completion rates and enjoyment. Use when asked 'enrichment stats', 'how are animals being enriched?', 'activity summary'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "animal_name": {"type": "string", "description": "Animal ID (optional — omit for shelter-wide)"}
                },
                "required": []
            }
        }
    },
]


def get_tool_definitions_for_provider(provider):
    """Return tool definitions formatted for the specific LLM provider."""
    if provider in ("OpenAI", "Groq", "Mistral", "DeepSeek"):
        return SCOUT_TOOLS
    elif provider == "Anthropic":
        # Anthropic uses a slightly different format
        tools = []
        for tool in SCOUT_TOOLS:
            tools.append({
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"],
            })
        return tools
    elif provider == "Google Gemini":
        # Gemini uses function_declarations
        declarations = []
        for tool in SCOUT_TOOLS:
            declarations.append({
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "parameters": tool["function"]["parameters"],
            })
        return [{"function_declarations": declarations}]
    elif provider == "Ollama (Local)":
        return SCOUT_TOOLS
    return SCOUT_TOOLS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL EXECUTION ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def execute_tool(tool_name, arguments):
    """Execute a tool call and return the result."""
    executors = {
        "create_animal_admission": _exec_create_admission,
        "update_animal_status": _exec_update_animal_status,
        "schedule_vet_appointment": _exec_schedule_vet_appointment,
        "assign_kennel": _exec_assign_kennel,
        "update_adoption_application": _exec_update_adoption_application,
        "create_veterinary_record": _exec_create_vet_record,
        "create_lost_and_found_report": _exec_create_lost_found,
        "generate_adoption_matches": _exec_adoption_matches,
        "run_lost_found_matching": _exec_lost_found_matching,
        "generate_social_media_post": _exec_social_media_post,
        "get_smart_kennel_recommendation": _exec_smart_kennel,
        "get_health_predictions": _exec_health_predictions,
        "get_donor_insights": _exec_donor_insights,
        "create_donation": _exec_create_donation,
        "get_adoption_score": _exec_adoption_score,
        "get_volunteer_schedule": _exec_volunteer_schedule,
        "get_volunteer_engagement": _exec_volunteer_engagement,
        "generate_platform_listing": _exec_platform_listing,
        "get_capacity_forecast": _exec_capacity_forecast,
        "get_inventory_status": _exec_inventory_status,
        "get_training_progress": _exec_training_progress,
        "get_medical_timeline": _exec_medical_timeline,
        "send_lost_pet_alert": _exec_send_lost_alert,
        "get_campaign_dashboard": _exec_campaign_dashboard,
        "get_enrichment_summary": _exec_enrichment_summary,
    }

    executor = executors.get(tool_name)
    if not executor:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        return executor(arguments)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Scout Tool Error: {tool_name}")
        return {"success": False, "error": "An internal error occurred while executing this action. Please try again or contact support."}


def _resolve_animal(identifier):
    """Resolve an animal identifier (ID or name) to the actual Animal docname."""
    if not identifier:
        return None
    # Try direct ID first
    if frappe.db.exists("Animal", identifier):
        return identifier
    # Try by animal_name
    matches = frappe.get_all("Animal", filters={"animal_name": ["like", f"%{identifier}%"],
        "status": ["not in", ["Adopted", "Transferred", "Deceased", "Returned to Owner"]]},
        fields=["name"], limit=1)
    if matches:
        return matches[0].name
    # Try broader search
    matches = frappe.get_all("Animal", filters={"animal_name": ["like", f"%{identifier}%"]},
        fields=["name"], order_by="creation desc", limit=1)
    return matches[0].name if matches else None


def _resolve_application(identifier):
    """Resolve an adoption application identifier."""
    if not identifier:
        return None
    if frappe.db.exists("Adoption Application", identifier):
        return identifier
    matches = frappe.get_all("Adoption Application",
        filters={"applicant_name": ["like", f"%{identifier}%"]},
        fields=["name"], order_by="creation desc", limit=1)
    return matches[0].name if matches else None


# ── TOOL EXECUTORS ───────────────────────────────────────

def _exec_create_admission(args):
    """Create a new animal admission."""
    from kennel_management.api import get_available_kennel

    # Parse estimated age
    age_years, age_months = 0, 0
    age_str = args.get("estimated_age", "")
    if age_str:
        age_lower = age_str.lower()
        import re
        y_match = re.search(r'(\d+)\s*(?:year|yr|y)', age_lower)
        m_match = re.search(r'(\d+)\s*(?:month|mo|m)', age_lower)
        if y_match:
            age_years = int(y_match.group(1))
        if m_match:
            age_months = int(m_match.group(1))
        if not y_match and not m_match:
            # Try just a number — assume years if > 1, months if <= 1
            num_match = re.search(r'(\d+)', age_lower)
            if num_match:
                val = int(num_match.group(1))
                if "pup" in age_lower or "kit" in age_lower or val <= 1:
                    age_months = max(val, 3)
                else:
                    age_years = val

    # Find a kennel
    requires_q = args.get("requires_quarantine", False)
    kennel = get_available_kennel(species=args.get("species"), requires_quarantine=requires_q)

    admission = frappe.get_doc({
        "doctype": "Animal Admission",
        "admission_date": today(),
        "admission_type": args.get("admission_type", "Stray"),
        "priority": "High" if args.get("condition_on_arrival") in ("Poor", "Critical") else "Medium",
        "animal_name_field": args.get("animal_name", "Unknown"),
        "species": args.get("species", "Dog"),
        "breed": args.get("breed"),
        "gender": args.get("gender", "Unknown"),
        "estimated_age": args.get("estimated_age"),
        "weight_on_arrival": args.get("weight_kg"),
        "color": args.get("color"),
        "condition_on_arrival": args.get("condition_on_arrival", "Fair"),
        "requires_quarantine": 1 if requires_q else 0,
        "assigned_kennel": kennel,
        "intake_notes": args.get("notes"),
        "surrenderer_name": args.get("surrenderer_name"),
        "surrenderer_phone": args.get("surrenderer_phone"),
    })
    admission.insert(ignore_permissions=True)

    kennel_name = ""
    if kennel:
        kennel_name = frappe.db.get_value("Kennel", kennel, "kennel_name") or kennel

    return {
        "success": True,
        "message": f"Admission created: {admission.name} for {args.get('animal_name', 'Unknown')} ({args.get('species', 'Dog')})",
        "admission_id": admission.name,
        "assigned_kennel": kennel_name,
        "url": f"/app/animal-admission/{admission.name}",
    }


def _exec_update_animal_status(args):
    """Update an animal's status."""
    animal_id = _resolve_animal(args.get("animal"))
    if not animal_id:
        return {"success": False, "error": f"Could not find animal: {args.get('animal')}"}

    valid_statuses = [
        "Available for Adoption", "Adopted", "In Foster Care", "Medical Hold",
        "Behavior Hold", "Quarantine", "Stray Hold", "In Treatment",
        "Reserved", "Transferred", "Deceased", "Returned to Owner", "Lost in Care",
    ]
    new_status = args.get("new_status", "")
    if new_status not in valid_statuses:
        return {"success": False, "error": f"Invalid status '{new_status}'. Valid: {', '.join(valid_statuses)}"}

    doc = frappe.get_doc("Animal", animal_id)
    old_status = doc.status

    # Prevent nonsensical transitions
    if old_status == "Deceased":
        return {"success": False, "error": f"{doc.animal_name} is marked as Deceased and cannot be updated."}

    doc.status = new_status

    if args.get("reason"):
        doc.add_comment("Comment", f"Status changed from {old_status} to {new_status}: {args['reason']}")

    doc.save(ignore_permissions=True)

    return {
        "success": True,
        "message": f"{doc.animal_name}'s status changed from **{old_status}** to **{args['new_status']}**",
        "animal_id": animal_id,
        "animal_name": doc.animal_name,
        "url": f"/app/animal/{animal_id}",
    }


def _exec_schedule_vet_appointment(args):
    """Schedule a veterinary appointment."""
    animal_id = _resolve_animal(args.get("animal"))
    if not animal_id:
        return {"success": False, "error": f"Could not find animal: {args.get('animal')}"}

    animal_name = frappe.db.get_value("Animal", animal_id, "animal_name")
    appt_date = args.get("appointment_date") or today()
    appt_time = args.get("appointment_time") or "09:00"

    appt = frappe.get_doc({
        "doctype": "Veterinary Appointment",
        "animal": animal_id,
        "animal_name": animal_name,
        "appointment_date": appt_date,
        "appointment_time": appt_time,
        "appointment_type": args.get("appointment_type", "Wellness Check"),
        "priority": args.get("priority", "Routine"),
        "status": "Scheduled",
        "notes": args.get("notes"),
        "veterinarian": args.get("veterinarian"),
    })
    appt.insert(ignore_permissions=True)

    return {
        "success": True,
        "message": f"Vet appointment scheduled: **{args.get('appointment_type')}** for **{animal_name}** on {appt_date} at {appt_time}",
        "appointment_id": appt.name,
        "url": f"/app/veterinary-appointment/{appt.name}",
    }


def _exec_assign_kennel(args):
    """Assign an animal to a kennel."""
    animal_id = _resolve_animal(args.get("animal"))
    if not animal_id:
        return {"success": False, "error": f"Could not find animal: {args.get('animal')}"}

    kennel_name = args.get("kennel")
    kennel_id = None

    if kennel_name:
        # Try to find the specific kennel
        kennel_id = frappe.db.get_value("Kennel", {"kennel_name": ["like", f"%{kennel_name}%"]}, "name")
        if not kennel_id:
            kennel_id = frappe.db.get_value("Kennel", kennel_name, "name")
        if not kennel_id:
            return {"success": False, "error": f"Could not find kennel: {kennel_name}"}

        # Check capacity
        kennel_doc = frappe.get_doc("Kennel", kennel_id)
        if kennel_doc.current_occupancy >= kennel_doc.capacity:
            return {"success": False, "error": f"Kennel {kennel_doc.kennel_name} is full ({kennel_doc.current_occupancy}/{kennel_doc.capacity})"}
    else:
        # Auto-assign
        from kennel_management.api import get_available_kennel
        species = frappe.db.get_value("Animal", animal_id, "species")
        kennel_id = get_available_kennel(
            species=species,
            requires_quarantine=args.get("requires_quarantine", False),
        )
        if not kennel_id:
            return {"success": False, "error": "No available kennels found"}

    animal_doc = frappe.get_doc("Animal", animal_id)
    old_kennel = animal_doc.current_kennel

    # Skip if already in the target kennel
    if old_kennel == kennel_id:
        kennel_display = frappe.db.get_value("Kennel", kennel_id, "kennel_name") or kennel_id
        return {"success": True, "message": f"**{animal_doc.animal_name}** is already in kennel **{kennel_display}**."}

    animal_doc.current_kennel = kennel_id
    animal_doc.save(ignore_permissions=True)

    # Update kennel occupancy counters
    if old_kennel and old_kennel != kennel_id:
        old_occ = frappe.db.get_value("Kennel", old_kennel, "current_occupancy") or 0
        frappe.db.set_value("Kennel", old_kennel, "current_occupancy", max(0, old_occ - 1))
    new_occ = frappe.db.get_value("Kennel", kennel_id, "current_occupancy") or 0
    frappe.db.set_value("Kennel", kennel_id, "current_occupancy", new_occ + 1)

    new_kennel_name = frappe.db.get_value("Kennel", kennel_id, "kennel_name") or kennel_id

    return {
        "success": True,
        "message": f"**{animal_doc.animal_name}** assigned to kennel **{new_kennel_name}**"
            + (f" (moved from {frappe.db.get_value('Kennel', old_kennel, 'kennel_name') or old_kennel})" if old_kennel else ""),
        "animal_id": animal_id,
        "kennel_id": kennel_id,
        "kennel_name": new_kennel_name,
    }


def _exec_update_adoption_application(args):
    """Update an adoption application status."""
    app_id = _resolve_application(args.get("application"))
    if not app_id:
        return {"success": False, "error": f"Could not find application: {args.get('application')}"}

    doc = frappe.get_doc("Adoption Application", app_id)
    old_status = doc.status
    doc.status = args["new_status"]

    if args.get("animal"):
        animal_id = _resolve_animal(args["animal"])
        if animal_id:
            doc.animal = animal_id
            doc.animal_name = frappe.db.get_value("Animal", animal_id, "animal_name")

    if args.get("notes"):
        doc.add_comment("Comment", args["notes"])

    if args["new_status"] == "Adoption Completed":
        doc.adoption_date = today()
        if doc.animal:
            animal_doc = frappe.get_doc("Animal", doc.animal)
            if animal_doc.status in ("Deceased", "Adopted", "Transferred"):
                return {
                    "success": False,
                    "error": f"Cannot complete adoption — {animal_doc.animal_name} is currently '{animal_doc.status}'."
                }
            animal_doc.status = "Adopted"
            animal_doc.outcome_type = "Adoption"
            animal_doc.outcome_date = today()
            animal_doc.save(ignore_permissions=True)

    doc.save(ignore_permissions=True)

    return {
        "success": True,
        "message": f"Application **{app_id}** ({doc.applicant_name}) updated from **{old_status}** to **{args['new_status']}**",
        "application_id": app_id,
        "url": f"/app/adoption-application/{app_id}",
    }


def _exec_create_vet_record(args):
    """Create a veterinary record."""
    animal_id = _resolve_animal(args.get("animal"))
    if not animal_id:
        return {"success": False, "error": f"Could not find animal: {args.get('animal')}"}

    animal_name = frappe.db.get_value("Animal", animal_id, "animal_name")

    record = frappe.get_doc({
        "doctype": "Veterinary Record",
        "animal": animal_id,
        "animal_name": animal_name,
        "date": today(),
        "record_type": args.get("record_type", "Examination"),
        "description": args.get("description"),
        "treatment": args.get("treatment"),
        "veterinarian": args.get("veterinarian"),
    })

    # Add vaccinations
    for vacc in (args.get("vaccinations") or []):
        record.append("vaccinations", {
            "vaccine_name": vacc.get("vaccine_name"),
            "date_administered": today(),
            "next_due_date": vacc.get("next_due_date"),
        })

    # Add medications
    for med in (args.get("medications") or []):
        record.append("medications", {
            "medication_name": med.get("medication_name"),
            "dosage": med.get("dosage"),
            "frequency": med.get("frequency"),
            "start_date": med.get("start_date") or today(),
            "end_date": med.get("end_date"),
        })

    record.insert(ignore_permissions=True)

    return {
        "success": True,
        "message": f"Vet record created: **{args.get('record_type')}** for **{animal_name}**",
        "record_id": record.name,
        "url": f"/app/veterinary-record/{record.name}",
    }


def _exec_create_lost_found(args):
    """Create a lost and found report."""
    report = frappe.get_doc({
        "doctype": "Lost and Found Report",
        "report_type": args.get("report_type", "Lost"),
        "status": "Open",
        "reporter_name": args.get("reporter_name"),
        "reporter_phone": args.get("reporter_phone"),
        "reporter_email": args.get("reporter_email"),
        "species": args.get("species"),
        "breed": args.get("breed"),
        "color": args.get("color"),
        "gender": args.get("gender"),
        "last_seen_location": args.get("last_seen_location"),
        "last_seen_date": args.get("last_seen_date") or today(),
        "description": args.get("description"),
        "microchip_number": args.get("microchip_number"),
    })
    report.insert(ignore_permissions=True)

    return {
        "success": True,
        "message": f"**{args.get('report_type')}** report created: {report.name} ({args.get('species', 'Unknown')})",
        "report_id": report.name,
        "url": f"/app/lost-and-found-report/{report.name}",
    }


def _exec_adoption_matches(args):
    """Run adoption matching engine."""
    from kennel_management.utils.ai_matching import compute_adoption_matches
    return compute_adoption_matches(
        animal=args.get("animal"),
        applicant=args.get("applicant"),
        top_n=args.get("top_n", 5),
    )


def _exec_lost_found_matching(args):
    """Run lost & found matching."""
    from kennel_management.utils.ai_matching import compute_lost_found_matches
    return compute_lost_found_matches(
        report=args.get("report"),
        animal=args.get("animal"),
    )


def _exec_social_media_post(args):
    """Generate social media content."""
    from kennel_management.utils.ai_content import generate_social_media_post
    return generate_social_media_post(
        animal=args.get("animal"),
        platform=args.get("platform", "general"),
        tone=args.get("tone", "heartwarming"),
        include_hashtags=args.get("include_hashtags", True),
    )


def _exec_smart_kennel(args):
    """Get smart kennel recommendation."""
    from kennel_management.utils.ai_analytics import recommend_kennel
    return recommend_kennel(args)


def _exec_health_predictions(args):
    """Get health predictions."""
    from kennel_management.utils.ai_analytics import get_health_predictions
    return get_health_predictions(animal=args.get("animal"))


def _exec_donor_insights(args):
    """Get donor intelligence."""
    from kennel_management.utils.ai_analytics import get_donor_insights
    return get_donor_insights(analysis_type=args.get("analysis_type", "overview"))


def _exec_create_donation(args):
    """Create a donation record."""
    amount = flt(args.get("amount", 0))
    if amount <= 0:
        return {"success": False, "error": "Donation amount must be a positive number."}
    if not args.get("donor_name"):
        return {"success": False, "error": "Donor name is required."}

    donation = frappe.get_doc({
        "doctype": "Donation",
        "donor_name": args.get("donor_name"),
        "amount": amount,
        "donation_type": args.get("donation_type", "Monetary"),
        "payment_method": args.get("payment_method"),
        "donation_date": today(),
        "notes": args.get("notes"),
    })
    donation.insert(ignore_permissions=True)

    return {
        "success": True,
        "message": f"Donation recorded: **R {amount:,.0f}** from **{args.get('donor_name')}** (saved as Draft for review)",
        "donation_id": donation.name,
        "url": f"/app/donation/{donation.name}",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NEW FEATURE TOOL EXECUTORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _exec_adoption_score(args):
    """Get adoption score for an animal or all animals."""
    from kennel_management.utils.adoption_scoring import compute_adoption_score, compute_all_adoption_scores

    animal_id = args.get("animal")
    if animal_id:
        resolved = _resolve_animal(animal_id)
        if not resolved:
            return {"success": False, "error": f"Could not find animal: {animal_id}"}
        result = compute_adoption_score(resolved)
        return {"success": True, **result}
    else:
        results = compute_all_adoption_scores()
        return {"success": True, **results}


def _exec_volunteer_schedule(args):
    """Get smart volunteer schedule suggestions."""
    from kennel_management.utils.volunteer_scheduling import get_volunteer_schedule_suggestions
    result = get_volunteer_schedule_suggestions()
    return {"success": True, **result}


def _exec_volunteer_engagement(args):
    """Get volunteer engagement analytics."""
    from kennel_management.utils.volunteer_scheduling import get_volunteer_engagement_report
    result = get_volunteer_engagement_report()
    return {"success": True, **result}


def _exec_platform_listing(args):
    """Generate adoption platform listings."""
    from kennel_management.utils.petfinder_sync import generate_bulk_listings
    result = generate_bulk_listings()
    return {"success": True, **result}


def _exec_capacity_forecast(args):
    """Get capacity forecast."""
    from kennel_management.utils.capacity_forecasting import get_capacity_forecast
    days = args.get("days_ahead", 14)
    result = get_capacity_forecast(int(days))
    return {"success": True, **result}


def _exec_inventory_status(args):
    """Get inventory dashboard."""
    from kennel_management.utils.inventory_management import get_inventory_dashboard
    result = get_inventory_dashboard()
    return {"success": True, **result}


def _exec_training_progress(args):
    """Get training progress for an animal or overview."""
    animal = args.get("animal_name")
    if animal:
        animal_id = _resolve_animal(animal)
        if not animal_id:
            return {"success": False, "error": f"Could not find animal: {animal}"}
        from kennel_management.utils.training_tracker import get_training_summary
        result = get_training_summary(animal_id)
    else:
        from kennel_management.utils.training_tracker import get_shelter_training_overview
        result = get_shelter_training_overview()
    return {"success": True, **result}


def _exec_medical_timeline(args):
    """Get medical timeline for an animal."""
    animal = args.get("animal_name")
    if not animal:
        return {"success": False, "error": "Animal name/ID is required"}
    animal_id = _resolve_animal(animal)
    if not animal_id:
        return {"success": False, "error": f"Could not find animal: {animal}"}
    from kennel_management.utils.medical_timeline import get_medical_timeline
    result = get_medical_timeline(animal_id)
    return {"success": True, **result}


def _exec_send_lost_alert(args):
    """Send lost pet community alert."""
    report = args.get("report_name")
    if not report:
        return {"success": False, "error": "Report name/ID is required"}
    from kennel_management.utils.lost_pet_alerts import send_lost_pet_alert
    result = send_lost_pet_alert(report)
    return {"success": True, **result}


def _exec_campaign_dashboard(args):
    """Get campaign dashboard."""
    from kennel_management.utils.campaign_builder import get_campaign_dashboard
    result = get_campaign_dashboard()
    return {"success": True, **result}


def _exec_enrichment_summary(args):
    """Get enrichment activity summary."""
    animal = args.get("animal_name")
    from kennel_management.utils.enrichment_scheduler import get_enrichment_summary
    result = get_enrichment_summary(animal)
    return {"success": True, **result}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM PROMPT ADDITION FOR FUNCTION CALLING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AGENT_SYSTEM_PROMPT_ADDITION = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛠️ AI AGENT ACTIONS — YOU CAN DO THINGS, NOT JUST TALK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You have access to powerful tools that let you take REAL actions in the shelter system.
When a user asks you to do something (not just look up info), USE YOUR TOOLS.

Available actions:
• **create_animal_admission** — Intake a new animal (stray, surrender, rescue, etc.)
• **update_animal_status** — Change status (adopt, quarantine, medical hold, etc.)
• **schedule_vet_appointment** — Book vet visits (exams, vaccines, surgery, etc.)
• **assign_kennel** — Move animals between kennels or auto-assign best fit
• **update_adoption_application** — Approve, reject, schedule home checks, complete adoptions
• **create_veterinary_record** — Log exam results, vaccinations, treatments, medications
• **create_lost_and_found_report** — File lost/found/sighted animal reports
• **generate_adoption_matches** — AI matching engine: find best animal-applicant pairs
• **run_lost_found_matching** — Cross-reference lost reports with shelter animals
• **generate_social_media_post** — Create adoption promotion posts for social media
• **get_smart_kennel_recommendation** — AI-optimized kennel placement suggestions
• **get_health_predictions** — Predictive health analytics and risk assessment
• **get_donor_insights** — Donation trends, lapsed donors, campaign analysis
• **create_donation** — Record a new donation
• **get_adoption_score** — Predictive adoption scoring: how likely is this animal to be adopted? Includes recommendations
• **get_volunteer_schedule** — Smart volunteer scheduling: who should help today based on skills + needs
• **get_volunteer_engagement** — Volunteer analytics: top volunteers, disengaged, skill inventory
• **generate_platform_listing** — Generate PetFinder/Adopt-a-Pet listings for available animals
• **get_capacity_forecast** — Predict shelter capacity trends and get occupancy recommendations
• **get_inventory_status** — Check supply levels, low stock alerts, and consumption rates
• **get_training_progress** — Training analytics and adoption-readiness scoring for animals
• **get_medical_timeline** — Full medical history timeline with vet visits, vaccinations, medications
• **send_lost_pet_alert** — Blast community alerts for lost/found pets with matching
• **get_campaign_dashboard** — Donation campaign progress, analytics, and fundraising totals
• **get_enrichment_summary** — Enrichment activity completion rates and enjoyment metrics

WHEN TO USE TOOLS:
- User says "admit this dog" → use create_animal_admission
- User says "mark Bella as adopted" → use update_animal_status
- User says "book a vet check for Rex" → use schedule_vet_appointment
- User says "who should adopt Bella?" → use generate_adoption_matches
- User says "write a Facebook post for Max" → use generate_social_media_post
- User says "where should we put this new cat?" → use get_smart_kennel_recommendation
- User says "any health concerns?" → use get_health_predictions
- User says "how are donations going?" → use get_donor_insights
- User says "how adoptable is Bella?" → use get_adoption_score
- User says "which animals need help getting adopted?" → use get_adoption_score (all)
- User says "who can volunteer today?" → use get_volunteer_schedule
- User says "volunteer stats" → use get_volunteer_engagement
- User says "update petfinder" → use generate_platform_listing

IMPORTANT:
- Always confirm what you did after executing an action (show the result)
- If you're unsure about parameters, ask the user before executing
- For destructive actions (status changes, adoptions), confirm with the user first unless they're clearly giving an instruction
- You can chain multiple tools in one response (e.g., create admission + assign kennel + schedule vet check)
"""
