import frappe
from frappe import _
from frappe.model.document import Document


class Donation(Document):
    def on_submit(self):
        if self.email and not self.receipt_sent:
            self.send_donation_receipt()

    def send_donation_receipt(self):
        try:
            frappe.sendmail(
                recipients=[self.email],
                subject=_("Thank You for Your Donation - {0}").format(self.name),
                message=_(
                    "Dear {0},<br><br>"
                    "Thank you for your generous {1} donation of {2} {3}.<br><br>"
                    "Your support helps us care for animals in need.<br><br>"
                    "Receipt Number: {4}<br>"
                    "Date: {5}<br><br>"
                    "With gratitude,<br>SPCA Team"
                ).format(
                    self.donor_name,
                    self.donation_type.lower(),
                    self.currency or "ZAR",
                    self.amount or "",
                    self.name,
                    self.donation_date,
                ),
                reference_doctype=self.doctype,
                reference_name=self.name,
            )
            self.db_set("receipt_sent", 1)
        except Exception:
            frappe.log_error(title=_("Failed to send donation receipt"))
