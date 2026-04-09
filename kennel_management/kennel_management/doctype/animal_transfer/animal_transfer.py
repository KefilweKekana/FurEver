import frappe
from frappe import _
from frappe.model.document import Document


class AnimalTransfer(Document):
    def on_submit(self):
        if self.animal:
            frappe.db.set_value("Animal", self.animal, {
                "status": "Transferred",
                "outcome_type": "Transfer",
                "outcome_date": self.transfer_date,
                "current_kennel": "",
            })
