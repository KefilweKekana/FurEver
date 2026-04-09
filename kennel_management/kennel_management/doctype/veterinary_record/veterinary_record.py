import frappe
from frappe import _
from frappe.model.document import Document


class VeterinaryRecord(Document):
    def validate(self):
        if self.record_type == "Vaccination" and not self.vaccinations:
            frappe.msgprint(_("Please add vaccination details."), indicator="orange")

    def on_submit(self):
        self.update_animal_vaccination_status()

    def update_animal_vaccination_status(self):
        if self.record_type == "Vaccination" and self.animal:
            # Track vaccination on the animal record
            frappe.get_doc(
                {
                    "doctype": "Comment",
                    "comment_type": "Info",
                    "reference_doctype": "Animal",
                    "reference_name": self.animal,
                    "content": _("Vaccination recorded: {0}").format(self.description or "See record"),
                }
            ).insert(ignore_permissions=True)
