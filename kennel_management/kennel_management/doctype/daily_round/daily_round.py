import frappe
from frappe import _
from frappe.model.document import Document


class DailyRound(Document):
    def validate(self):
        self.calculate_summary()

    def calculate_summary(self):
        self.total_animals_checked = len(self.animals) if self.animals else 0
        attention_count = sum(
            1 for a in (self.animals or []) if a.needs_attention
        )
        self.animals_needing_attention = attention_count

    def on_submit(self):
        self.flag_animals_needing_attention()

    def flag_animals_needing_attention(self):
        for detail in self.animals or []:
            if detail.needs_attention and detail.animal:
                frappe.get_doc(
                    {
                        "doctype": "Comment",
                        "comment_type": "Info",
                        "reference_doctype": "Animal",
                        "reference_name": detail.animal,
                        "content": _(
                            "Flagged during {0} round on {1}: {2}"
                        ).format(
                            self.round_type, self.date, detail.attention_reason or "Needs attention"
                        ),
                    }
                ).insert(ignore_permissions=True)
