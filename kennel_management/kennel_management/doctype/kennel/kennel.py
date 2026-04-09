import frappe
from frappe import _
from frappe.model.document import Document


class Kennel(Document):
    def validate(self):
        if self.current_occupancy > self.capacity:
            frappe.throw(
                _("Current occupancy ({0}) cannot exceed capacity ({1}).").format(
                    self.current_occupancy, self.capacity
                )
            )

    def get_animals(self):
        return frappe.get_all(
            "Animal",
            filters={
                "current_kennel": self.name,
                "status": [
                    "not in",
                    ["Adopted", "Transferred", "Deceased", "Returned to Owner"],
                ],
            },
            fields=["name", "animal_name", "species", "breed", "status"],
        )

    @property
    def is_full(self):
        return self.current_occupancy >= self.capacity

    @property
    def available_spots(self):
        return max(0, self.capacity - self.current_occupancy)
