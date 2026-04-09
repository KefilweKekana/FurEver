import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, date_diff, getdate, cint


class Animal(Document):
    def validate(self):
        self.validate_age()
        self.validate_kennel()
        self.update_size_from_weight()

    def validate_age(self):
        if self.date_of_birth and getdate(self.date_of_birth) > getdate(today()):
            frappe.throw(_("Date of Birth cannot be in the future."))

        if self.date_of_birth:
            days = date_diff(today(), self.date_of_birth)
            self.estimated_age_years = days // 365
            self.estimated_age_months = (days % 365) // 30

    def validate_kennel(self):
        if self.current_kennel:
            kennel = frappe.get_doc("Kennel", self.current_kennel)
            if kennel.status == "Maintenance":
                frappe.throw(
                    _("Kennel {0} is under maintenance and cannot be assigned.").format(
                        self.current_kennel
                    )
                )

    def update_size_from_weight(self):
        if self.weight_kg and self.species == "Dog" and not self.size:
            if self.weight_kg < 5:
                self.size = "Tiny (< 5kg)"
            elif self.weight_kg < 10:
                self.size = "Small (5-10kg)"
            elif self.weight_kg < 25:
                self.size = "Medium (10-25kg)"
            elif self.weight_kg < 45:
                self.size = "Large (25-45kg)"
            else:
                self.size = "Giant (> 45kg)"

    def on_update(self):
        self.update_kennel_occupancy()
        if self.has_value_changed("status"):
            self.log_status_change()

    def update_kennel_occupancy(self):
        if self.current_kennel:
            kennel = frappe.get_doc("Kennel", self.current_kennel)
            count = frappe.db.count(
                "Animal",
                filters={
                    "current_kennel": self.current_kennel,
                    "status": [
                        "not in",
                        ["Adopted", "Transferred", "Deceased", "Returned to Owner"],
                    ],
                },
            )
            kennel.db_set("current_occupancy", count)
            kennel.db_set(
                "status", "Occupied" if count > 0 else "Available", update_modified=False
            )

    def log_status_change(self):
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Animal",
                "reference_name": self.name,
                "content": _("Status changed to {0}").format(self.status),
            }
        ).insert(ignore_permissions=True)

    def get_vaccination_history(self):
        return frappe.get_all(
            "Veterinary Record",
            filters={"animal": self.name, "record_type": "Vaccination"},
            fields=["name", "date", "description", "veterinarian"],
            order_by="date desc",
        )

    def get_medical_history(self):
        return frappe.get_all(
            "Veterinary Record",
            filters={"animal": self.name},
            fields=["name", "date", "record_type", "description", "veterinarian"],
            order_by="date desc",
        )

    @property
    def days_in_shelter(self):
        if self.intake_date:
            end_date = self.outcome_date or today()
            return date_diff(end_date, self.intake_date)
        return 0
