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
            if kennel.status in ("Maintenance", "Out of Service"):
                frappe.throw(
                    _("Kennel {0} is {1} and cannot be assigned.").format(
                        self.current_kennel, kennel.status.lower()
                    )
                )
            if kennel.status == "Cleaning":
                frappe.throw(
                    _("Kennel {0} is being cleaned. Mark it as Available before assigning animals.").format(
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
        self._update_old_kennel()
        self.update_kennel_occupancy()
        if self.has_value_changed("status"):
            self.log_status_change()

    def _update_old_kennel(self):
        """When animal moves to a different kennel, update the old one."""
        old = self.get_doc_before_save()
        if not old:
            return
        old_kennel = old.get("current_kennel")
        new_kennel = self.current_kennel
        if old_kennel and old_kennel != new_kennel:
            self._refresh_kennel_status(old_kennel)

    def update_kennel_occupancy(self):
        if self.current_kennel:
            self._refresh_kennel_status(self.current_kennel)

    def _refresh_kennel_status(self, kennel_name):
        """Recalculate occupancy and auto-set status for a kennel."""
        kennel = frappe.get_doc("Kennel", kennel_name)
        count = frappe.db.count(
            "Animal",
            filters={
                "current_kennel": kennel_name,
                "status": [
                    "not in",
                    ["Adopted", "Transferred", "Deceased", "Returned to Owner"],
                ],
            },
        )
        kennel.db_set("current_occupancy", count)

        # Don't override Maintenance, Reserved, or Out of Service
        if kennel.status in ("Maintenance", "Reserved", "Out of Service"):
            return

        if count == 0 and kennel.status not in ("Available", "Cleaning"):
            # Kennel just emptied — schedule for cleaning
            kennel.db_set("status", "Cleaning", update_modified=False)
            frappe.msgprint(
                _("Kennel {0} is now empty and has been scheduled for cleaning.").format(kennel_name),
                indicator="yellow",
                alert=True,
            )
        elif count == 0 and kennel.status == "Cleaning":
            # Already in cleaning, keep it
            pass
        elif count >= kennel.capacity:
            kennel.db_set("status", "Full", update_modified=False)
        else:
            kennel.db_set("status", "Occupied", update_modified=False)

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
