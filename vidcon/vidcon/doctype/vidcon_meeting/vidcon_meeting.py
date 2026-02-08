# Copyright (c) 2026, Pema and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds, get_time


class VidConMeeting(Document):
	def validate(self):
		self.calculate_duration()
		
	def before_save(self):
		if self.is_new():
			self.create_google_meet_event()
		else:
			self.update_google_meet_event()
	
	def on_trash(self):
		"""Clean up Google Calendar Event and Meet subscription when meeting is deleted"""
		# Delete Google Calendar Event
		if self.event:
			try:
				event_doc = frappe.get_doc("Event", self.event)
				event_doc.delete(ignore_permissions=True)
				frappe.logger().info(f"Deleted Event {self.event} for meeting {self.name}")
			except Exception as e:
				frappe.log_error(f"Error deleting Event {self.event}: {str(e)}")
		
		# Delete Meet Events subscription
		if self.meet_subscription_id:
			try:
				from vidcon.vidcon.doctype.vidcon_meeting.meet_utils import delete_space_subscription
				delete_space_subscription(self.meet_subscription_id)
				frappe.logger().info(f"Deleted subscription {self.meet_subscription_id} for meeting {self.name}")
			except Exception as e:
				frappe.log_error(f"Error deleting subscription {self.meet_subscription_id}: {str(e)}")
	
	def calculate_duration(self):
		"""Calculate meeting duration in minutes"""
		if self.start_time and self.end_time:
			start = get_time(self.start_time)
			end = get_time(self.end_time)
			
			# Convert to datetime for calculation
			from datetime import datetime, timedelta
			start_dt = datetime.combine(datetime.today(), start)
			end_dt = datetime.combine(datetime.today(), end)
			
			# Handle overnight meetings
			if end_dt < start_dt:
				end_dt += timedelta(days=1)
			
			duration_seconds = (end_dt - start_dt).total_seconds()
			self.duration = int(duration_seconds / 60)
	
	def create_google_meet_event(self):
		"""Create a Google Calendar Event with Meet link"""
		if not self.event:
			settings = frappe.get_single("VidCon Settings")
			
			if not settings.google_calendar:
				frappe.throw(_("Please configure Google Calendar in VidCon Settings"))
			
			# Get the Google Calendar document
			google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
			
			# Combine date and time for starts_on and ends_on
			from datetime import datetime
			from frappe.utils import getdate
			meeting_date = getdate(self.meeting_date)
			starts_on = datetime.combine(meeting_date, get_time(self.start_time))
			ends_on = datetime.combine(meeting_date, get_time(self.end_time))
			
			# Create Event document
			event = frappe.get_doc({
				"doctype": "Event",
				"subject": self.title,
				"description": self.description or "",
				"starts_on": starts_on,
				"ends_on": ends_on,
				"event_type": "Private",
				"add_video_conferencing": 1,
				"sync_with_google_calendar": 1,
				"google_calendar": settings.google_calendar,
				"status": "Open"
			})
			
			# Add attendees to event
			if self.attendees:
				for attendee in self.attendees:
					# Only add to event_participants if we have reference fields
					# Otherwise, Event will just use the email for invitations
					if attendee.reference_doctype and attendee.reference_docname:
						event.append("event_participants", {
							"email": attendee.email,
							"reference_doctype": attendee.reference_doctype,
							"reference_docname": attendee.reference_docname
						})
			
			event.insert(ignore_permissions=True)
			
			# Link the event to this meeting
			self.event = event.name
			
			# The google_meet_link will be populated after the event syncs with Google
			# We'll fetch it in after_insert
	
	def after_insert(self):
		"""Fetch Google Meet link and create subscription after event is created"""
		if self.event:
			# Trigger sync to Google Calendar and create subscription
			frappe.enqueue(
				"vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.sync_event_and_fetch_meet_link",
				meeting=self.name,
				queue="short"
			)
	
	def update_google_meet_event(self):
		"""Update the linked Google Calendar Event"""
		if self.event and self.has_value_changed("title") or self.has_value_changed("description") or \
		   self.has_value_changed("meeting_date") or self.has_value_changed("start_time") or \
		   self.has_value_changed("end_time"):
			
			event = frappe.get_doc("Event", self.event)
			
			from datetime import datetime
			from frappe.utils import getdate
			meeting_date = getdate(self.meeting_date)
			starts_on = datetime.combine(meeting_date, get_time(self.start_time))
			ends_on = datetime.combine(meeting_date, get_time(self.end_time))
			
			event.subject = self.title
			event.description = self.description or ""
			event.starts_on = starts_on
			event.ends_on = ends_on
			
			# Update attendees
			event.event_participants = []
			if self.attendees:
				for attendee in self.attendees:
					# Only add to event_participants if we have reference fields
					if attendee.reference_doctype and attendee.reference_docname:
						event.append("event_participants", {
							"email": attendee.email,
							"reference_doctype": attendee.reference_doctype,
							"reference_docname": attendee.reference_docname
						})
			
			event.save(ignore_permissions=True)


@frappe.whitelist()
def sync_event_and_fetch_meet_link(meeting):
	"""Background job to sync event and fetch Meet link"""
	try:
		meeting_doc = frappe.get_doc("VidCon Meeting", meeting)
		
		if not meeting_doc.event:
			return
		
		event_doc = frappe.get_doc("Event", meeting_doc.event)
		
		# Check if event has google_meet_link
		if event_doc.google_meet_link:
			# Extract space_id from Meet link
			# Format: https://meet.google.com/abc-defg-hij
			space_id = event_doc.google_meet_link.split('/')[-1] if event_doc.google_meet_link else None
			
			frappe.db.set_value("VidCon Meeting", meeting, {
				"google_meet_link": event_doc.google_meet_link,
				"google_calendar_event_id": event_doc.google_calendar_event_id,
				"google_space_id": space_id
			}, update_modified=False)
			frappe.db.commit()
			
			# Create Meet Events subscription if enabled
			settings = frappe.get_single("VidCon Settings")
			if settings.enable_meet_events and not meeting_doc.meet_subscription_id:
				from vidcon.vidcon.doctype.vidcon_meeting.meet_utils import create_space_subscription
				
				# Reload to get updated fields
				meeting_doc.reload()
				response = create_space_subscription(meeting_doc)
				
				if response:
					frappe.db.set_value("VidCon Meeting", meeting, "meet_subscription_id", 
						response.get("name"), update_modified=False)
					frappe.db.commit()
					frappe.logger().info(f"Created Meet subscription for {meeting}: {response.get('name')}")
		else:
			# Event might not be synced yet, retry after a few seconds
			frappe.enqueue(
				"vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.sync_event_and_fetch_meet_link",
				meeting=meeting,
				queue="short",
				at_front=False,
				enqueue_after_commit=True
			)
	except Exception as e:
		frappe.log_error(f"Error syncing Meet link for {meeting}: {str(e)}")


@frappe.whitelist()
def create_meet_subscription(meeting_name):
	"""Create a Meet Events subscription for this meeting"""
	from vidcon.vidcon.doctype.vidcon_meeting.meet_utils import create_space_subscription
	
	meeting = frappe.get_doc("VidCon Meeting", meeting_name)
	meeting.check_permission("write")
	
	response = create_space_subscription(meeting)
	
	if response:
		# Store subscription ID on meeting
		meeting.db_set("meet_subscription_id", response.get("name"), update_modified=False)
		
		return {
			"subscription_id": response.get("name"),
			"state": response.get("state")
		}
	else:
		frappe.throw(_("Failed to create subscription. Check Error Log for details."))


@frappe.whitelist()
def check_subscription_status(meeting_name):
	"""Check the status of a meeting's subscription"""
	from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import get_subscription_status
	
	meeting = frappe.get_doc("VidCon Meeting", meeting_name)
	meeting.check_permission("read")
	
	if not meeting.meet_subscription_id:
		frappe.throw(_("No subscription found for this meeting"))
	
	settings = frappe.get_single("VidCon Settings")
	
	status = get_subscription_status(
		google_calendar_name=settings.google_calendar,
		subscription_id=meeting.meet_subscription_id
	)
	
	return {
		"subscription_id": meeting.meet_subscription_id,
		"state": status.get("state") if status else "UNKNOWN"
	}
