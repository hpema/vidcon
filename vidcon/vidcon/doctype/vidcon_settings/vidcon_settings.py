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
			
			if not self.meeting_organizer_email:
				frappe.throw(_("Meeting Organizer Email is required to enable Meet Events"))
			if not self.pubsub_topic_name:
				frappe.throw(_("Pub/Sub Topic Name is required to enable Meet Events. Format: projects/PROJECT_ID/topics/meet-events"))
	
	def on_update(self):
		# Handle subscription creation/deletion based on enable_meet_events checkbox
		if self.has_value_changed("enable_meet_events"):
			if self.enable_meet_events:
				# Create subscription
				self.create_meet_subscription()
			else:
				# Delete subscription
				self.delete_meet_subscription()
	
	def create_meet_subscription(self):
		"""Create Google Workspace Events subscription for Meet events"""
		try:
			from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import create_meet_subscription
			
			frappe.msgprint(_("Creating Meet Events subscription..."), alert=True)
			
			# Create subscription
			response = create_meet_subscription(
				google_calendar_name=self.google_calendar,
				user_email=self.meeting_organizer_email,
				pubsub_topic=self.pubsub_topic_name
			)
			
			# Store subscription details
			self.db_set("meet_subscription_id", response.get("name"), update_modified=False)
			self.db_set("subscription_target_user", self.meeting_organizer_email, update_modified=False)
			self.db_set("meet_subscription_state", response.get("state"), update_modified=False)
			
			frappe.msgprint(_("Meet Events subscription created successfully!"), alert=True, indicator="green")
			
		except Exception as e:
			frappe.log_error(title="Meet Subscription Creation Failed", message=str(e))
			frappe.throw(_("Failed to create Meet Events subscription: {0}").format(str(e)))
	
	def delete_meet_subscription(self):
		"""Delete Google Workspace Events subscription"""
		if not self.meet_subscription_id:
			return
		
		try:
			from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import delete_meet_subscription
			
			frappe.msgprint(_("Deleting Meet Events subscription..."), alert=True)
			
			# Delete subscription
			delete_meet_subscription(
				google_calendar_name=self.google_calendar,
				subscription_id=self.meet_subscription_id
			)
			
			# Clear subscription details
			self.db_set("meet_subscription_id", None, update_modified=False)
			self.db_set("subscription_target_user", None, update_modified=False)
			self.db_set("meet_subscription_state", None, update_modified=False)
			
			frappe.msgprint(_("Meet Events subscription deleted successfully!"), alert=True, indicator="green")
			
		except Exception as e:
			frappe.log_error(title="Meet Subscription Deletion Failed", message=str(e))
			frappe.throw(_("Failed to delete Meet Events subscription: {0}").format(str(e)))
