import frappe
from frappe import _
from frappe.model.document import Document


class KennelManagementSettings(Document):
	def validate(self):
		self.validate_ai_settings()
		self.validate_temperature()

	def validate_ai_settings(self):
		if self.enable_ai_chatbot:
			if not self.ai_provider:
				frappe.throw(_("Please select an AI Provider when AI Chatbot is enabled"))
			if self.ai_provider != "Ollama (Local)" and not self.ai_api_key:
				frappe.throw(_("API Key is required for {0}").format(self.ai_provider))

	def validate_temperature(self):
		if self.ai_temperature is not None:
			if self.ai_temperature < 0 or self.ai_temperature > 2:
				frappe.throw(_("AI Temperature must be between 0.0 and 2.0"))
