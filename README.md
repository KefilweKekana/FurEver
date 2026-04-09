# 🐾 SPCA Kennel Management System

A comprehensive kennel management system built for SPCAs (Society for the Prevention of Cruelty to Animals) as a custom ERPNext v16 app. Manage animal intake, adoptions, veterinary care, daily operations, volunteers, donations, and community engagement — all from one place.

## Features

### 🐕 Animal Management
- **Animal Registry** — Complete animal profiles with photos, medical history, behavior, and compatibility tracking
- **Kennel Management** — Track kennel occupancy, capacity, types (indoor/outdoor/isolation/quarantine), and features
- **Kennel Cards** — Printable door cards showing animal info, compatibility icons, and status at a glance

### 📋 Intake & Admissions
- **Animal Admission** — Submittable intake form supporting stray, owner surrender, rescue, transfer, confiscation, and more
- **Condition Assessment** — Body condition scoring (1–9), injury tracking, vaccination/microchip/spay status
- **Auto-quarantine** — Strays automatically flagged for quarantine with configurable hold periods
- **Auto Vet Scheduling** — Initial vet exam automatically created on admission

### 🏠 Adoptions & Fostering
- **Adoption Applications** — Full workflow: Pending → Under Review → Home Check → Approved → Completed
- **Adoption Certificate** — Beautiful printable adoption certificate with paw-print watermark
- **Foster Applications** — Short/medium/long-term, medical, neonatal, behavior, and hospice fostering
- **Application Web Forms** — Public-facing forms for adoption and foster applications

### 🩺 Veterinary Care
- **Appointments** — Full appointment system with types (vaccination, surgery, dental, emergency, etc.)
- **Physical Examination** — Vitals tracking (temperature, heart rate, respiratory rate, weight, BCS, pain score)
- **Diagnosis & Treatment** — Examination notes, medications table, procedures, surgery notes, lab results
- **Veterinary Records** — Permanent medical records with vaccination history
- **Vaccination Certificates** — Official printable certificates with lot numbers and next-due dates
- **Follow-up Scheduling** — Automatic follow-up appointment creation

### 📊 Daily Operations
- **Daily Rounds** — Structured inspection rounds with per-animal checks
- **Animal Checks** — Food/water consumption, stool quality, behavior notes, health notes, kennel cleanliness
- **Attention Flagging** — Animals needing attention are highlighted and summarized
- **Behavior Assessments** — Comprehensive temperament, sociability, and trainability scoring
- **Feeding Schedules** — Per-animal dietary plans with allergies and supplements

### 💬 CRM & Communications
- **SMS Integration** — Twilio, BulkSMS, Clickatell, Africa's Talking, or custom gateway
- **WhatsApp Integration** — Meta Cloud API, Twilio, 360dialog, or custom
- **Email Notifications** — Automated emails for status updates, reminders, and receipts
- **Message Templates** — Pre-built SMS and email templates for all key events
- **Communication Buttons** — Quick send email/SMS/WhatsApp from adoption applications

### 🌐 Public Website
- **Available Animals Page** — Browse adoptable animals with filters (species, size, gender, search)
- **Adoption Application** — Public web form with comprehensive household/experience questions
- **Foster Application** — Public web form for foster parents
- **Volunteer Sign-up** — Public web form for volunteer registration
- **Lost & Found Reports** — Public reporting with automatic microchip matching
- **Donation Form** — Online donation form with dedicated-to and campaign options
- **Success Pages** — Branded thank-you pages for all form submissions

### 💰 Donations & Fundraising
- **Donation Tracking** — Monetary and supplies, campaigns, dedications
- **Tax Receipts** — Section 18A tax-deductible receipt generation
- **Printable Receipts** — Official donation receipt print format

### 👥 Volunteer Management
- **Volunteer Registry** — Skills, availability, compliance tracking
- **Background Checks** — Orientation, training, and waiver tracking
- **Hours Logging** — Track volunteer service hours

### 🔄 Transfers
- **Animal Transfers** — Track transfers between facilities with transport details
- **Transfer Documentation** — Full audit trail of animal movements

### 📈 Reports & Dashboard
- **Shelter Statistics** — Census, species breakdown, kennel occupancy, monthly activity
- **Adoption Report** — Applications by status, average time-to-adopt, fee collection
- **Kennel Occupancy Report** — Stacked bar chart of capacity vs occupancy
- **Veterinary Activity Report** — Appointment types, vet workload, costs, emergencies
- **Module Dashboard** — Quick-access workspace with shortcuts and links

### 🖨️ Print Formats
- **SPCA Admission Form** — Official intake document with condition assessment
- **Adoption Certificate** — Elegant adoption certificate with animal photo
- **Medical Record Card** — Complete vet visit record with vitals grid
- **Kennel Card** — Door card with photo, status, and compatibility icons
- **Vaccination Certificate** — Official vaccination record with lot tracking
- **Donation Receipt** — Tax receipt with Section 18A notice
- **Daily Round Report** — Inspection summary with attention flags

## Installation

### Prerequisites
- ERPNext v16 (Frappe Framework v16)
- Python 3.10+
- MariaDB 10.6+ or PostgreSQL 13+

### Install

```bash
# Navigate to your bench directory
cd ~/frappe-bench

# Get the app from your repository
bench get-app kennel_management /path/to/kennel_management
# OR from git:
# bench get-app kennel_management https://github.com/your-org/kennel_management.git

# Install on your site
bench --site your-site.local install-app kennel_management

# Run migrations
bench --site your-site.local migrate

# Build assets
bench build --app kennel_management

# Restart
bench restart
```

### Post-Installation Setup

1. **Navigate to:** Kennel Management Settings
2. **Configure:**
   - Shelter name and contact details
   - SMS provider (Twilio/BulkSMS/Clickatell/AfricasTalking/Custom)
   - WhatsApp provider (Meta Cloud API/Twilio)
   - Default adoption fees
   - Quarantine periods
   - Capacity warning thresholds
3. **Create Roles:** System Manager, Kennel Manager, Kennel Staff, Veterinarian, Volunteer
4. **Set up Kennels:** Create kennel records with capacity, type, and section
5. **Import Data:** Import existing animal records if migrating from another system

## Roles & Permissions

| Role | Access |
|------|--------|
| **System Manager** | Full access to all features and settings |
| **Kennel Manager** | Animals, admissions, adoptions, kennels, reports, volunteers |
| **Kennel Staff** | Animals (read/write), daily rounds, feeding, behavior assessments |
| **Veterinarian** | Animals (read), vet appointments, records, medications |
| **Volunteer** | Limited animal access (read), daily rounds (read) |
| **Website User** | Public web forms (adoption, foster, volunteer, donate, lost & found) |

## SMS / WhatsApp Configuration

### Twilio
1. Create a Twilio account at https://www.twilio.com
2. Get your Account SID and Auth Token
3. Set up a phone number for SMS/WhatsApp
4. Enter credentials in Kennel Management Settings

### BulkSMS (South Africa)
1. Register at https://www.bulksms.com
2. Get your API Token
3. Enter in Kennel Management Settings

### Meta WhatsApp Business API
1. Set up a Meta Business account
2. Create a WhatsApp Business App
3. Get Phone Number ID and Access Token
4. Create message templates in Meta Business Manager
5. Enter credentials in Kennel Management Settings

## Currency

Default currency is **ZAR** (South African Rand). Change in ERPNext settings if needed.

## File Structure

```
kennel_management/
├── kennel_management/
│   ├── api.py                          # Whitelisted API methods
│   ├── hooks.py                        # App hooks & configuration
│   ├── tasks.py                        # Scheduled tasks
│   ├── notifications.py                # Notification config
│   ├── permissions.py                  # Custom permissions
│   ├── config/
│   │   └── desktop.py                  # Module card config
│   ├── events/                         # Document event handlers
│   │   ├── admission.py
│   │   ├── adoption.py
│   │   ├── veterinary.py
│   │   └── animal.py
│   ├── utils/
│   │   ├── messaging.py                # SMS & WhatsApp integration
│   │   └── jinja_methods.py            # Template helpers
│   ├── templates/
│   │   ├── emails/                     # Email templates
│   │   └── sms_templates.py            # SMS message templates
│   ├── www/                            # Public web pages
│   │   ├── available-animals.html
│   │   └── [success pages].html
│   └── kennel_management/
│       ├── doctype/                    # 19 DocTypes
│       │   ├── animal/
│       │   ├── animal_admission/
│       │   ├── adoption_application/
│       │   ├── kennel/
│       │   ├── veterinary_appointment/
│       │   ├── veterinary_record/
│       │   ├── daily_round/
│       │   ├── behavior_assessment/
│       │   ├── feeding_schedule/
│       │   ├── volunteer/
│       │   ├── donation/
│       │   ├── lost_and_found_report/
│       │   ├── foster_application/
│       │   ├── animal_transfer/
│       │   ├── kennel_management_settings/
│       │   ├── animal_photo/            (child table)
│       │   ├── daily_round_detail/      (child table)
│       │   ├── medication_item/         (child table)
│       │   └── vaccination_item/        (child table)
│       ├── print_format/               # 7 Print Formats
│       │   ├── spca_admission_form/
│       │   ├── spca_adoption_certificate/
│       │   ├── spca_medical_record_card/
│       │   ├── spca_kennel_card/
│       │   ├── spca_vaccination_certificate/
│       │   ├── spca_donation_receipt/
│       │   └── spca_daily_round_report/
│       ├── web_form/                   # 5 Web Forms
│       │   ├── adoption_application/
│       │   ├── lost_and_found/
│       │   ├── volunteer_signup/
│       │   ├── foster_application/
│       │   └── donate/
│       ├── report/                     # 4 Script Reports
│       │   ├── shelter_statistics/
│       │   ├── adoption_report/
│       │   ├── kennel_occupancy_report/
│       │   └── veterinary_activity_report/
│       └── workspace/
│           └── kennel_management/       # Module workspace
├── setup.py
├── requirements.txt
├── MANIFEST.in
├── license.txt
└── README.md
```

## Scheduled Tasks

| Frequency | Task | Description |
|-----------|------|-------------|
| Daily | `send_daily_kennel_summary` | Email summary of shelter census and activity |
| Daily | `check_vaccination_reminders` | Alert for upcoming/overdue vaccinations |
| Daily | `check_followup_reminders` | Alert for overdue vet follow-ups |
| Hourly | `send_appointment_reminders` | Remind staff of upcoming vet appointments |
| Weekly | `send_weekly_adoption_report` | Weekly adoption statistics summary |
| 8:00 AM | `send_morning_feeding_reminder` | Morning feeding round notification |
| 5:00 PM | `send_evening_feeding_reminder` | Evening feeding round notification |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License — see [license.txt](license.txt) for details.

## Support

For support, email admin@spca.org or create an issue in the repository.

---

Built with ❤️ for SPCA shelters everywhere. Every animal deserves a loving home. 🐾
