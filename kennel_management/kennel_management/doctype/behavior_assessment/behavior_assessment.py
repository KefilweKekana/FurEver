import frappe
from frappe import _
from frappe.model.document import Document


class BehaviorAssessment(Document):
    def validate(self):
        self.set_assessment_number()

    def set_assessment_number(self):
        if not self.assessment_number and self.animal:
            count = frappe.db.count(
                "Behavior Assessment",
                filters={"animal": self.animal, "name": ["!=", self.name]},
            )
            self.assessment_number = count + 1

    def on_update(self):
        if self.status == "Completed" and self.animal:
            self.update_animal_behavior()

    def update_animal_behavior(self):
        animal = frappe.get_doc("Animal", self.animal)
        updates = {}
        if self.overall_temperament:
            updates["temperament"] = self.overall_temperament
        if self.energy_level:
            updates["energy_level"] = self.energy_level
        if self.dog_sociability:
            mapping = {"Highly Social": "Yes", "Neutral": "With Introduction", "Reactive": "No", "Aggressive": "No", "Selectively Social": "With Introduction"}
            updates["good_with_dogs"] = mapping.get(self.dog_sociability, "Unknown")
        if self.child_reaction:
            mapping = {"Excellent": "Yes", "Good": "Yes", "Cautious": "Older Children Only", "Fearful": "No", "Not Recommended": "No"}
            updates["good_with_children"] = mapping.get(self.child_reaction, "Unknown")
        if self.house_training:
            mapping = {"Fully Trained": "Yes", "Mostly Trained": "In Progress", "In Progress": "In Progress", "Not Trained": "No"}
            updates["house_trained"] = mapping.get(self.house_training, "Unknown")
        if self.leash_behavior:
            mapping = {"Excellent": "Yes", "Good": "Yes", "Pulls": "In Progress", "Reactive on Leash": "No", "Refuses": "No"}
            updates["leash_trained"] = mapping.get(self.leash_behavior, "Unknown")

        for field, value in updates.items():
            animal.db_set(field, value, update_modified=False)
