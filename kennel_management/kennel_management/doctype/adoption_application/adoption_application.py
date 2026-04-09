import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, add_days


class AdoptionApplication(Document):
    def validate(self):
        self.validate_animal_availability()
        self.validate_landlord_permission()

    def validate_animal_availability(self):
        if self.animal:
            animal = frappe.get_doc("Animal", self.animal)
            if animal.status not in ["Available for Adoption", "Reserved"]:
                frappe.throw(
                    _("Animal {0} ({1}) is not available for adoption. Current status: {2}").format(
                        animal.animal_name, self.animal, animal.status
                    )
                )

    def validate_landlord_permission(self):
        if self.own_or_rent == "Rent" and self.landlord_allows_pets == "No":
            frappe.throw(
                _("Application cannot proceed if landlord does not allow pets.")
            )

    def on_submit(self):
        if self.status == "Approved":
            self.complete_adoption()
        self.send_status_notification()

    def on_update(self):
        if self.has_value_changed("status"):
            self.send_status_notification()

    def complete_adoption(self):
        if not self.animal:
            frappe.throw(_("Please select an animal to complete the adoption."))

        if not self.adoption_fee_paid:
            frappe.throw(_("Adoption fee must be paid before completing adoption."))

        if not self.adoption_contract_signed:
            frappe.throw(
                _("Adoption contract must be signed before completing adoption.")
            )

        # Update animal status
        animal = frappe.get_doc("Animal", self.animal)
        animal.status = "Adopted"
        animal.outcome_type = "Adoption"
        animal.outcome_date = self.adoption_date or today()
        animal.adoption_fee = self.adoption_fee
        animal.save(ignore_permissions=True)

        self.db_set("status", "Adoption Completed")

        # Schedule follow-up
        if not self.followup_date:
            self.db_set("followup_date", add_days(today(), 14))

    def send_status_notification(self):
        status_messages = {
            "Under Review": _("Your adoption application for {0} is now under review."),
            "Approved": _("Congratulations! Your adoption application for {0} has been approved!"),
            "Rejected": _("We're sorry, your adoption application for {0} has not been approved at this time."),
            "Home Check Scheduled": _("A home check has been scheduled for your adoption application for {0}."),
            "Adoption Completed": _("Adoption of {0} is now complete. Welcome to your new family member!"),
        }

        animal_name = self.animal_name or "your chosen pet"
        message = status_messages.get(self.status)

        if message and self.email:
            try:
                frappe.sendmail(
                    recipients=[self.email],
                    subject=_("Adoption Application Update - {0}").format(self.name),
                    message=message.format(animal_name),
                    reference_doctype=self.doctype,
                    reference_name=self.name,
                )
            except Exception:
                frappe.log_error(
                    title=_("Failed to send adoption notification"),
                    message=frappe.get_traceback(),
                )

        # Send SMS if configured
        if self.phone:
            self.send_sms_update(message, animal_name)

        # Send WhatsApp if configured
        if self.whatsapp_number:
            self.send_whatsapp_update(message, animal_name)

    def send_sms_update(self, message, animal_name):
        if not message:
            return
        try:
            from kennel_management.utils.messaging import send_sms

            send_sms(self.phone, message.format(animal_name))
        except ImportError:
            pass
        except Exception:
            frappe.log_error(
                title=_("Failed to send SMS"),
                message=frappe.get_traceback(),
            )

    def send_whatsapp_update(self, message, animal_name):
        if not message:
            return
        try:
            from kennel_management.utils.messaging import send_whatsapp

            send_whatsapp(self.whatsapp_number, message.format(animal_name))
        except ImportError:
            pass
        except Exception:
            frappe.log_error(
                title=_("Failed to send WhatsApp message"),
                message=frappe.get_traceback(),
            )
