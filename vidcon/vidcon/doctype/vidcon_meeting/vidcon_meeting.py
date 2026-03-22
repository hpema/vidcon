# Copyright (c) 2026, Pema and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds, get_time, getdate
from datetime import datetime, timedelta


class VidConMeeting(Document):
	def validate(self):
		self.calculate_duration()
		
	def after_insert(self):
		"""Create Google Calendar event after meeting is inserted"""
		self.create_google_calendar_event()
		
	def on_update(self):
		"""Update Google Calendar event when meeting is updated"""
		if not self.is_new() and self.google_calendar_event_id:
			if (self.has_value_changed("title") or self.has_value_changed("description") or 
				self.has_value_changed("meeting_date") or self.has_value_changed("start_time") or 
				self.has_value_changed("end_time") or self.has_value_changed("attendees")):
				self.update_google_calendar_event()
	
	def on_trash(self):
		"""Clean up Google Calendar Event, Event Logs, and Meet subscription when meeting is deleted"""
		# Clear links from VidCon Event Logs first
		try:
			event_logs = frappe.get_all(
				"VidCon Event Log",
				filters={"meeting": self.name},
				fields=["name"]
			)
			for log in event_logs:
				frappe.db.set_value("VidCon Event Log", log.name, "meeting", None)
			if event_logs:
				frappe.db.commit()
		except Exception as e:
			frappe.log_error(title="Error Unlinking Event Logs", message=str(e))
		
		# Delete Google Calendar Event directly via API
		if self.google_calendar_event_id:
			try:
				self.delete_google_calendar_event()
			except Exception as e:
				frappe.log_error(title="Error Deleting Google Calendar Event", message=str(e))
		
		# Delete Meet Events subscription
		if self.meet_subscription_id:
			try:
				from vidcon.vidcon.doctype.vidcon_meeting.meet_utils import delete_space_subscription
				delete_space_subscription(self.meet_subscription_id)
			except Exception as e:
				frappe.log_error(title="Error Deleting Subscription", message=str(e))
	
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
	
	def create_google_calendar_event(self):
		"""Create a Google Calendar event directly via API with Meet link"""
		if self.google_calendar_event_id:
			return  # Already created
			
		settings = frappe.get_single("VidCon Settings")
		
		if not settings.google_calendar:
			frappe.throw(_("Please configure Google Calendar in VidCon Settings"))
		
		try:
			from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
			
			google_calendar, account = get_google_calendar_object(settings.google_calendar)
			
			# Build event data
			meeting_date = getdate(self.meeting_date)
			starts_on = datetime.combine(meeting_date, get_time(self.start_time))
			ends_on = datetime.combine(meeting_date, get_time(self.end_time))
			
			# Build attendees list
			attendees = []
			if self.attendees:
				for attendee in self.attendees:
					if attendee.email:
						attendees.append({"email": attendee.email})
			
			# Create event with Google Meet
			event_data = {
				"summary": self.title,
				"description": self.description or "",
				"start": {
					"dateTime": starts_on.isoformat(),
					"timeZone": frappe.utils.get_system_timezone()
				},
				"end": {
					"dateTime": ends_on.isoformat(),
					"timeZone": frappe.utils.get_system_timezone()
				},
				"attendees": attendees,
				"conferenceData": {
					"createRequest": {
						"requestId": self.name,
						"conferenceSolutionKey": {"type": "hangoutsMeet"}
					}
				}
			}
			
			# Create event in Google Calendar
			created_event = google_calendar.events().insert(
				calendarId=account.google_calendar_id,
				body=event_data,
				conferenceDataVersion=1,
				sendUpdates="all"
			).execute()
			
			# Extract Meet link and space ID
			meet_link = created_event.get("hangoutLink")
			event_id = created_event.get("id")
			space_id = meet_link.split("/")[-1] if meet_link else None
			
			# Update meeting with Google Calendar data
			frappe.db.set_value("VidCon Meeting", self.name, {
				"google_meet_link": meet_link,
				"google_calendar_event_id": event_id,
				"google_space_id": space_id
			}, update_modified=False)
			frappe.db.commit()
			
			# Reload to get updated fields
			self.reload()
			
			# Create Meet subscription if enabled
			if settings.enable_meet_events and space_id:
				from vidcon.vidcon.doctype.vidcon_meeting.meet_utils import create_space_subscription
				response = create_space_subscription(self)
				if response:
					frappe.db.set_value("VidCon Meeting", self.name, "meet_subscription_id", 
						response.get("name"), update_modified=False)
					frappe.db.commit()
			
			print(f"✓ Created Google Calendar event with Meet link: {meet_link}")
			
		except Exception as e:
			frappe.log_error(
				title=f"Failed to create Google Calendar event - {self.name}",
				message=str(e)
			)
			frappe.throw(_("Failed to create Google Calendar event. Check Error Log for details."))
	
	
	def update_google_calendar_event(self):
		"""Update the Google Calendar event directly via API"""
		if not self.google_calendar_event_id:
			return
			
		settings = frappe.get_single("VidCon Settings")
		
		if not settings.google_calendar:
			return
			
		try:
			from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
			
			google_calendar, account = get_google_calendar_object(settings.google_calendar)
			
			# Get existing event
			event = google_calendar.events().get(
				calendarId=account.google_calendar_id,
				eventId=self.google_calendar_event_id
			).execute()
			
			# Update event data
			meeting_date = getdate(self.meeting_date)
			starts_on = datetime.combine(meeting_date, get_time(self.start_time))
			ends_on = datetime.combine(meeting_date, get_time(self.end_time))
			
			event["summary"] = self.title
			event["description"] = self.description or ""
			event["start"] = {
				"dateTime": starts_on.isoformat(),
				"timeZone": frappe.utils.get_system_timezone()
			}
			event["end"] = {
				"dateTime": ends_on.isoformat(),
				"timeZone": frappe.utils.get_system_timezone()
			}
			
			# Update attendees
			attendees = []
			if self.attendees:
				for attendee in self.attendees:
					if attendee.email:
						attendees.append({"email": attendee.email})
			event["attendees"] = attendees
			
			# Update event in Google Calendar
			google_calendar.events().update(
				calendarId=account.google_calendar_id,
				eventId=self.google_calendar_event_id,
				body=event,
				sendUpdates="all"
			).execute()
			
			print(f"✓ Updated Google Calendar event")
			
		except Exception as e:
			frappe.log_error(
				title=f"Failed to update Google Calendar event - {self.name}",
				message=str(e)
			)
			print(f"✗ Failed to update Google Calendar event: {str(e)}")


	def delete_google_calendar_event(self):
		"""Delete the Google Calendar event directly via API"""
		if not self.google_calendar_event_id:
			return
			
		settings = frappe.get_single("VidCon Settings")
		
		if not settings.google_calendar:
			return
			
		try:
			from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
			
			google_calendar, account = get_google_calendar_object(settings.google_calendar)
			
			# Delete event from Google Calendar
			google_calendar.events().delete(
				calendarId=account.google_calendar_id,
				eventId=self.google_calendar_event_id,
				sendUpdates="all"
			).execute()
			
			print(f"✓ Deleted Google Calendar event")
			
		except Exception as e:
			frappe.log_error(
				title=f"Failed to delete Google Calendar event - {self.name}",
				message=str(e)
			)
			print(f"✗ Failed to delete Google Calendar event: {str(e)}")




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
