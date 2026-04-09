import frappe
from frappe import _
from frappe.model.document import Document


class LostAndFoundReport(Document):
    def on_update(self):
        if self.has_value_changed("status"):
            self.notify_reporter()
            if self.status == "Matched" and self.microchip_number:
                self.try_match_by_microchip()

    def try_match_by_microchip(self):
        if not self.microchip_number:
            return
        animal = frappe.db.get_value(
            "Animal",
            filters={"microchip_number": self.microchip_number},
            fieldname="name",
        )
        if animal and not self.matched_animal:
            self.db_set("matched_animal", animal)

    def notify_reporter(self):
        if not self.reporter_email:
            return

        status_messages = {
            "Investigating": _("We are actively investigating your {0} pet report."),
            "Matched": _("Great news! We may have found a match for your {0} pet report."),
            "Reunited": _("Your {0} pet report has been resolved - pet reunited!"),
            "Closed": _("Your {0} pet report has been closed."),
        }

        message = status_messages.get(self.status)
        if message:
            try:
                frappe.sendmail(
                    recipients=[self.reporter_email],
                    subject=_("Lost & Found Update - {0}").format(self.name),
                    message=message.format(self.report_type.lower()),
                    reference_doctype=self.doctype,
                    reference_name=self.name,
                )
            except Exception:
                frappe.log_error(title=_("Failed to send Lost & Found notification"))
