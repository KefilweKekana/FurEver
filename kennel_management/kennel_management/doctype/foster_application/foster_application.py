import frappe
from frappe import _
from frappe.model.document import Document


class FosterApplication(Document):
    def on_update(self):
        if self.has_value_changed("status"):
            if self.status == "Active" and self.animal:
                frappe.db.set_value("Animal", self.animal, "status", "In Foster Care")
                frappe.db.set_value("Animal", self.animal, "current_foster", self.name)
            elif self.status == "Completed" and self.animal:
                frappe.db.set_value("Animal", self.animal, "status", "Available for Adoption")
                frappe.db.set_value("Animal", self.animal, "current_foster", "")
            self.send_status_email()

    def send_status_email(self):
        if not self.email:
            return
        try:
            frappe.sendmail(
                recipients=[self.email],
                subject=_("Foster Application Update - {0}").format(self.name),
                message=_("Your foster application status has been updated to: {0}").format(self.status),
                reference_doctype=self.doctype,
                reference_name=self.name,
            )
        except Exception:
            frappe.log_error(title=_("Failed to send foster notification"))
