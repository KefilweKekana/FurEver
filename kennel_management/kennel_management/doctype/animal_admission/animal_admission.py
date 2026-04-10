import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, add_days, nowdate


class AnimalAdmission(Document):
    def validate(self):
        self.validate_kennel_availability()

    def validate_kennel_availability(self):
        if self.assigned_kennel:
            kennel = frappe.get_doc("Kennel", self.assigned_kennel)
            if kennel.status in ("Maintenance", "Out of Service"):
                frappe.throw(
                    _("Kennel {0} is {1} and cannot be assigned.").format(
                        self.assigned_kennel, kennel.status.lower()
                    )
                )
            if kennel.status == "Cleaning":
                frappe.throw(
                    _("Kennel {0} is being cleaned. Mark it as Available before assigning animals.").format(
                        self.assigned_kennel
                    )
                )
            if kennel.is_full:
                frappe.throw(
                    _("Kennel {0} is at full capacity ({1}/{2}).").format(
                        self.assigned_kennel, kennel.current_occupancy, kennel.capacity
                    )
                )

    def on_submit(self):
        self.create_or_update_animal_record()
        self.db_set("status", "Completed")
        self.send_admission_notification()

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    def create_or_update_animal_record(self):
        if self.animal:
            # Update existing animal
            animal = frappe.get_doc("Animal", self.animal)
            animal.current_kennel = self.assigned_kennel
            animal.intake_date = nowdate()
            animal.source = self.admission_type
            animal.status = "Quarantine" if self.requires_quarantine else "Stray Hold"
            animal.save(ignore_permissions=True)
        else:
            # Create new animal record
            animal = frappe.get_doc(
                {
                    "doctype": "Animal",
                    "animal_name": self.animal_name_field,
                    "species": self.species,
                    "breed": self.breed,
                    "color": self.color,
                    "gender": self.gender,
                    "weight_kg": self.weight_on_arrival,
                    "animal_photo": self.animal_photo,
                    "intake_date": nowdate(),
                    "source": self.admission_type,
                    "current_kennel": self.assigned_kennel,
                    "temperament": self.initial_temperament,
                    "status": "Quarantine" if self.requires_quarantine else "Stray Hold",
                    "spay_neuter_status": self.get_spay_status(),
                }
            )
            animal.insert(ignore_permissions=True)
            self.db_set("animal", animal.name)

            # Schedule initial vet check
            if self.assigned_veterinarian:
                self.create_initial_vet_appointment(animal.name)

    def get_spay_status(self):
        mapping = {"Yes": "Spayed", "No": "Intact", "Unknown": ""}
        return mapping.get(self.is_spayed_neutered, "")

    def create_initial_vet_appointment(self, animal_name):
        frappe.get_doc(
            {
                "doctype": "Veterinary Appointment",
                "animal": animal_name,
                "animal_name": self.animal_name_field,
                "appointment_date": today(),
                "appointment_type": "Intake Examination",
                "veterinarian": self.assigned_veterinarian,
                "reason": _("Initial intake examination for admission {0}").format(
                    self.name
                ),
                "status": "Scheduled",
            }
        ).insert(ignore_permissions=True)

    def send_admission_notification(self):
        # Send notification to kennel manager
        frappe.publish_realtime(
            "new_admission",
            {
                "admission": self.name,
                "animal_name": self.animal_name_field,
                "species": self.species,
                "admission_type": self.admission_type,
            },
        )
