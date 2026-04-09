import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, add_days, get_datetime, now_datetime


class VeterinaryAppointment(Document):
    def validate(self):
        self.validate_date()
        self.validate_veterinarian_availability()

    def validate_date(self):
        if self.appointment_date and self.status == "Scheduled":
            if str(self.appointment_date) < today():
                frappe.msgprint(
                    _("Appointment date is in the past."), indicator="orange", alert=True
                )

    def validate_veterinarian_availability(self):
        if self.veterinarian and self.appointment_date and self.appointment_time:
            existing = frappe.db.count(
                "Veterinary Appointment",
                filters={
                    "veterinarian": self.veterinarian,
                    "appointment_date": self.appointment_date,
                    "appointment_time": self.appointment_time,
                    "status": ["not in", ["Cancelled", "No Show", "Rescheduled"]],
                    "name": ["!=", self.name],
                },
            )
            if existing:
                frappe.msgprint(
                    _("Veterinarian {0} already has an appointment at this time.").format(
                        self.veterinarian
                    ),
                    indicator="orange",
                    alert=True,
                )

    def on_submit(self):
        if self.status == "Completed":
            self.create_veterinary_record()
            self.update_animal_weight()
            if self.followup_required and self.followup_date:
                self.create_followup_appointment()

    def on_update(self):
        if self.has_value_changed("status"):
            if self.status == "Completed":
                self.update_animal_weight()

    def create_veterinary_record(self):
        record = frappe.get_doc(
            {
                "doctype": "Veterinary Record",
                "animal": self.animal,
                "animal_name": self.animal_name,
                "date": self.appointment_date,
                "veterinarian": self.veterinarian,
                "record_type": self.get_record_type(),
                "description": self.diagnosis or self.examination_notes,
                "treatment": self.treatment_plan,
                "notes": self.notes,
                "source_appointment": self.name,
            }
        )
        record.insert(ignore_permissions=True)
        record.submit()

    def get_record_type(self):
        type_map = {
            "Vaccination": "Vaccination",
            "Spay/Neuter": "Surgery",
            "Surgery": "Surgery",
            "Dental": "Treatment",
            "Lab Work": "Lab Results",
            "X-Ray/Imaging": "Lab Results",
            "Microchipping": "Treatment",
        }
        return type_map.get(self.appointment_type, "Examination")

    def update_animal_weight(self):
        if self.weight_kg and self.animal:
            frappe.db.set_value("Animal", self.animal, "weight_kg", self.weight_kg)

    def create_followup_appointment(self):
        frappe.get_doc(
            {
                "doctype": "Veterinary Appointment",
                "animal": self.animal,
                "animal_name": self.animal_name,
                "appointment_date": self.followup_date,
                "appointment_type": "Follow-up",
                "veterinarian": self.veterinarian,
                "reason": _("Follow-up for appointment {0}. {1}").format(
                    self.name, self.followup_notes or ""
                ),
                "status": "Scheduled",
            }
        ).insert(ignore_permissions=True)
