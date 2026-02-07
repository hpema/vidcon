# Copyright (c) 2026, Pema and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url


class VidConSettings(Document):
	def validate(self):
		if self.enable_webhook:
			self.webhook_url = get_url() + "/api/method/vidcon.api.webhook.google_calendar_webhook"
