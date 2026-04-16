app_name = "kennel_management"
app_title = "Kennel Management"
app_publisher = "SPCA"
app_description = "Comprehensive SPCA Kennel Management System"
app_email = "admin@spca.org"
app_license = "MIT"
app_version = "1.1.0"

# Required Apps
required_apps = ["frappe"]

# App Icon & Color
app_icon = "octicon octicon-heart"
app_color = "#e74c3c"

# -------------------------------------------------------------------------------
# Client Scripts
# -------------------------------------------------------------------------------
app_include_js = [
    "/assets/kennel_management/js/kennel_redirect.js",
    "/assets/kennel_management/js/kennel_chatbot.js",
]
app_include_css = [
    "/assets/kennel_management/css/kennel_chatbot.css",
]

# -------------------------------------------------------------------------------
# Website
# -------------------------------------------------------------------------------
website_route_rules = [
    {"from_route": "/adoption-application", "to_route": "adoption-application"},
    {"from_route": "/lost-and-found", "to_route": "lost-and-found"},
    {"from_route": "/volunteer-signup", "to_route": "volunteer-signup"},
    {"from_route": "/foster-application", "to_route": "foster-application"},
    {"from_route": "/available-animals", "to_route": "available-animals"},
    {"from_route": "/donate", "to_route": "donate"},
    {"from_route": "/ask-scout", "to_route": "ask-scout"},
    {"from_route": "/foster-portal", "to_route": "foster-portal"},
]

# -------------------------------------------------------------------------------
# DocType JS Includes
# -------------------------------------------------------------------------------
# doctype_js = {}
# doctype_list_js = {}
# doctype_tree_js = {}
# doctype_calendar_js = {}

# -------------------------------------------------------------------------------
# Scheduled Tasks (Cron)
# -------------------------------------------------------------------------------
scheduler_events = {
    "daily": [
        "kennel_management.tasks.send_daily_kennel_summary",
        "kennel_management.tasks.check_vaccination_reminders",
        "kennel_management.tasks.check_followup_reminders",
        "kennel_management.tasks.flag_long_stay_animals",
        "kennel_management.tasks.check_kennel_capacity_alerts",
        "kennel_management.tasks.generate_post_adoption_followups",
        "kennel_management.tasks.auto_match_lost_and_found",
        "kennel_management.tasks.generate_daily_briefing",
        "kennel_management.tasks.check_length_of_stay_alerts",
        "kennel_management.tasks.sync_adoption_platforms",
    ],
    "hourly": [
        "kennel_management.tasks.send_appointment_reminders",
    ],
    "weekly": [
        "kennel_management.tasks.send_weekly_adoption_report",
        "kennel_management.tasks.generate_weekly_intelligence_report",
    ],
    "cron": {
        "0 7 * * *": [  # Every day at 7 AM - daily rounds + morning feeding
            "kennel_management.tasks.auto_generate_daily_rounds",
            "kennel_management.tasks.send_morning_feeding_reminder",
        ],
        "0 8 * * *": [  # Every day at 8 AM - check morning feeding overdue
            "kennel_management.tasks.check_morning_feeding_overdue",
        ],
        "0 15 * * *": [  # Every day at 3 PM - afternoon feeding
            "kennel_management.tasks.send_evening_feeding_reminder",
        ],
        "0 16 * * *": [  # Every day at 4 PM - check afternoon feeding overdue
            "kennel_management.tasks.check_afternoon_feeding_overdue",
        ],
    },
}

# -------------------------------------------------------------------------------
# Notification Configuration
# -------------------------------------------------------------------------------
notification_config = "kennel_management.notifications.get_notification_config"

# -------------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------------
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["module", "=", "Kennel Management"]],
    },
    {
        "doctype": "Property Setter",
        "filters": [["module", "=", "Kennel Management"]],
    },
    {
        "doctype": "Print Format",
        "filters": [["module", "=", "Kennel Management"]],
    },
    {
        "doctype": "Notification",
        "filters": [["module", "=", "Kennel Management"]],
    },
    {
        "doctype": "Web Form",
        "filters": [["module", "=", "Kennel Management"]],
    },
]

# -------------------------------------------------------------------------------
# Document Events
# -------------------------------------------------------------------------------
doc_events = {
    "Animal Admission": {
        "on_submit": [
            "kennel_management.events.admission.on_submit",
            "kennel_management.events.admission.auto_match_lost_found_on_intake",
        ],
        "on_cancel": "kennel_management.events.admission.on_cancel",
    },
    "Adoption Application": {
        "on_update": "kennel_management.events.adoption.on_update",
        "on_submit": "kennel_management.events.adoption.on_submit",
    },
    "Veterinary Appointment": {
        "on_submit": "kennel_management.events.veterinary.on_appointment_submit",
        "on_update": "kennel_management.events.veterinary.on_appointment_update",
    },
    "Animal": {
        "on_update": "kennel_management.events.animal.on_update",
    },
}

# -------------------------------------------------------------------------------
# Permissions
# -------------------------------------------------------------------------------
has_permission = {
    "Animal": "kennel_management.permissions.animal_permission",
}

# -------------------------------------------------------------------------------
# Jinja Customization
# -------------------------------------------------------------------------------
jinja = {
    "methods": [
        "kennel_management.utils.jinja_methods.get_animal_age",
        "kennel_management.utils.jinja_methods.get_kennel_occupancy_color",
    ],
}

# -------------------------------------------------------------------------------
# Override Standard DocType Classes
# -------------------------------------------------------------------------------
# override_doctype_class = {}

# -------------------------------------------------------------------------------
# Portal Menu Items
# -------------------------------------------------------------------------------
standard_portal_menu_items = [
    {
        "title": "Available Animals",
        "route": "/available-animals",
        "role": "",
    },
    {
        "title": "My Adoption Applications",
        "route": "/adoption-application",
        "role": "Website User",
    },
    {
        "title": "Ask Scout",
        "route": "/ask-scout",
        "role": "",
    },
    {
        "title": "Foster Portal",
        "route": "/foster-portal",
        "role": "Website User",
    },
]

# -------------------------------------------------------------------------------
# Boot Session
# -------------------------------------------------------------------------------
# boot_session = "kennel_management.startup.boot_session"

# -------------------------------------------------------------------------------
# On Session Creation
# -------------------------------------------------------------------------------
on_session_creation = []
on_logout = []
