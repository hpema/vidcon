# Copyright (c) 2026, Pema and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, now_datetime


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
				# Create global user-based subscription
				self.create_meet_subscription()
			else:
				# Delete subscription
				self.delete_meet_subscription()
	
	def create_meet_subscription(self):
		"""Create Google Workspace Events subscription for user's Meet events"""
		try:
			from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import create_meet_subscription
			
			frappe.msgprint(_("Creating Meet Events subscription..."), alert=True)
			
			# Create user-based subscription (monitors all meetings for this user)
			response = create_meet_subscription(
				google_calendar_name=self.google_calendar,
				user_email=self.meeting_organizer_email,
				pubsub_topic=self.pubsub_topic_name
			)
			
			# Store subscription details
			self.db_set("meet_subscription_id", response.get("name"), update_modified=False)
			self.db_set("subscription_target_user", self.meeting_organizer_email, update_modified=False)
			self.db_set("meet_subscription_state", response.get("state"), update_modified=False)
			
			frappe.msgprint(_("Meet Events subscription created successfully! All meetings organized by {0} will be monitored.").format(self.meeting_organizer_email), 
				alert=True, indicator="green")
			
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


@frappe.whitelist()
def test_webhook_endpoint():
	"""
	Test the Pub/Sub webhook endpoint by sending a test message.
	This verifies that the endpoint is accessible and processing messages.
	"""
	import requests
	import base64
	import json
	
	settings = frappe.get_single("VidCon Settings")
	endpoint_url = settings.pubsub_subscription_endpoint
	
	# Create a test Pub/Sub message
	test_event = {
		"@type": "type.googleapis.com/google.apps.events.subscriptions.v1.EventPayload",
		"eventType": "google.workspace.meet.conference.v2.started",
		"conferenceRecord": {
			"name": "conferenceRecords/test-conference-123",
			"startTime": now_datetime().isoformat()
		}
	}
	
	# Encode as base64 (Pub/Sub format)
	test_data = base64.b64encode(json.dumps(test_event).encode()).decode()
	
	# Create Pub/Sub envelope
	pubsub_message = {
		"message": {
			"data": test_data,
			"messageId": "test-message-" + frappe.generate_hash(length=10),
			"publishTime": now_datetime().isoformat() + "Z"
		}
	}
	
	try:
		# Send POST request to webhook
		response = requests.post(
			endpoint_url,
			json=pubsub_message,
			headers={"Content-Type": "application/json"},
			timeout=10
		)
		
		if response.status_code == 200:
			# Check if event was logged
			recent_events = frappe.get_all(
				"VidCon Event Log",
				filters={"event_type": "google.workspace.meet.conference.v2.started"},
				order_by="received_at desc",
				limit=1
			)
			
			if recent_events:
				return {
					"success": True,
					"message": "Webhook test successful! Event was received and logged.",
					"event_log_id": recent_events[0].name,
					"status_code": response.status_code
				}
			else:
				return {
					"success": False,
					"message": "Webhook responded but event was not logged. Check Error Log.",
					"status_code": response.status_code
				}
		else:
			return {
				"success": False,
				"message": f"Webhook returned error: {response.status_code}",
				"status_code": response.status_code,
				"response": response.text[:500]
			}
			
	except Exception as e:
		frappe.log_error(title="Webhook Test Failed", message=str(e))
		return {
			"success": False,
			"message": f"Failed to reach webhook: {str(e)}"
		}


@frappe.whitelist()
def get_recent_events_status():
	"""
	Get status of recent events to show in VidCon Settings.
	"""
	# Get last 5 events
	events = frappe.get_all(
		"VidCon Event Log",
		fields=["name", "event_type", "received_at", "status"],
		order_by="received_at desc",
		limit=5
	)
	
	# Get total event count
	total_events = frappe.db.count("VidCon Event Log")
	
	# Get last event time
	last_event = events[0] if events else None
	
	return {
		"total_events": total_events,
		"last_event_time": last_event.get("received_at") if last_event else None,
		"recent_events": events
	}
