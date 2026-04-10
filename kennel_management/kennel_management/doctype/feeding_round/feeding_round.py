# Copyright (c) 2025, SPCA and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowtime


class FeedingRound(Document):
	def validate(self):
		self.calculate_summary()

	def calculate_summary(self):
		total = len(self.animals) if self.animals else 0
		fed = sum(1 for row in (self.animals or []) if row.fed)
		self.total_animals = total
		self.animals_fed = fed
		self.animals_unfed = total - fed
		self.completion_percentage = (fed / total * 100) if total else 0

		if fed == total and total > 0:
			self.status = "Completed"
		elif fed > 0:
			self.status = "In Progress"

	def on_submit(self):
		self.calculate_summary()
		self.create_feeding_logs()
		if self.animals_unfed > 0:
			self.flag_unfed_animals()

	def create_feeding_logs(self):
		"""Create individual Feeding Log records for each fed animal."""
		for row in self.animals:
			if not row.fed:
				continue
			# Find linked feeding schedule
			schedule = frappe.db.get_value(
				"Feeding Schedule",
				{"animal": row.animal, "status": "Active"},
				"name"
			)
			log = frappe.new_doc("Feeding Log")
			log.animal = row.animal
			log.feeding_schedule = schedule
			log.date = self.date
			log.time = row.fed_time or nowtime()
			log.meal_type = "Breakfast" if "Morning" in (self.shift or "") else "Lunch"
			log.food_type = row.food_type
			log.consumption_level = row.consumption_level or "All"
			log.fed_by = row.fed_by
			log.special_notes = row.notes
			log.insert(ignore_permissions=True)

	def flag_unfed_animals(self):
		"""Send notification about animals that were not fed."""
		unfed = [row.animal_name or row.animal for row in self.animals if not row.fed]
		if unfed:
			frappe.publish_realtime(
				"feeding_alert",
				{
					"title": f"Feeding Round {self.name} - Unfed Animals",
					"message": f"{len(unfed)} animal(s) not fed during {self.shift}: {', '.join(unfed[:10])}",
					"shift": self.shift,
					"count": len(unfed),
				}
			)
