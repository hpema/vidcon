# Copyright (c) 2026, Pema and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url


class VidConSettings(Document):
	def validate(self):
		# Auto-populate Pub/Sub subscription endpoint
		self.pubsub_subscription_endpoint = get_url() + "/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push"
		
		# Validate required fields for Meet Events
		if self.enable_meet_events:
			if not self.google_calendar:
				frappe.throw(_("Google Calendar is required to enable Meet Events"))
			
			# Check if Google Calendar is authorized
			# Frappe stores refresh_token (permanent) and generates access_token on demand
			has_refresh_token = frappe.db.exists("__Auth", {
				"doctype": "Google Calendar",
				"name": self.google_calendar,
				"fieldname": "refresh_token"
			})
			
			if not has_refresh_token:
				frappe.throw(_(
					"Google Calendar '{0}' is not authorized. Please open the Google Calendar document and click 'Authorize API Access' before enabling Meet Events."
				).format(self.google_calendar))
			
			if not self.pubsub_topic_name:
				frappe.throw(_("Pub/Sub Topic Name is required to enable Meet Events. Format: projects/PROJECT_ID/topics/meet-events"))
	
	def on_update(self):
		# When Meet Events is enabled, show success message
		# Subscriptions are created per meeting, not globally
		if self.has_value_changed("enable_meet_events"):
			if self.enable_meet_events:
				frappe.msgprint(_(
					"Meet Events enabled! Subscriptions will be created automatically for each VidCon Meeting with a Google Meet link."
				), alert=True, indicator="green")
