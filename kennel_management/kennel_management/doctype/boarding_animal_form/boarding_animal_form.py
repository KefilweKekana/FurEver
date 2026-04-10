import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, date_diff, flt


class BoardingAnimalForm(Document):
    def validate(self):
        self.calculate_costs()

    def calculate_costs(self):
        """Auto-calculate total and outstanding from dates and cost per day."""
        if self.date_in and self.date_out and self.cost_per_day:
            days = date_diff(self.date_out, self.date_in)
            if days < 1:
                days = 1
            self.total_cost = flt(self.cost_per_day) * days
            self.outstanding = flt(self.total_cost) - flt(self.amount_paid)
