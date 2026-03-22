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


@frappe.whitelist()
def sync_from_google_meet(meeting_name):
	"""Sync meeting status, times, and transcript from Google Meet API"""
	meeting = frappe.get_doc("VidCon Meeting", meeting_name)
	meeting.check_permission("write")
	
	if not meeting.google_space_id:
		frappe.throw(_("No Google Meet space ID found. Meeting may not have been created properly."))
	
	try:
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
		from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import get_vidcon_access_token
		
		settings = frappe.get_single("VidCon Settings")
		if not settings.google_calendar:
			frappe.throw(_("Please configure Google Calendar in VidCon Settings"))
		
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		google_settings = frappe.get_single("Google Settings")
		
		# Build credentials
		credentials = Credentials(
			token=get_vidcon_access_token(settings.google_calendar),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		# Build Meet API service
		meet_service = build('meet', 'v2', credentials=credentials, static_discovery=False)
		
		updates = []
		
		# Try to find conference record by space_id
		space_name = f"spaces/{meeting.google_space_id}"
		
		try:
			# List conference records for this space
			conferences_response = meet_service.conferenceRecords().list(
				filter=f'space.name="{space_name}"'
			).execute()
			
			conferences = conferences_response.get('conferenceRecords', [])
			
			if conferences:
				# Get the most recent conference
				conference = conferences[0]
				conference_id = conference.get('name', '').split('/')[-1]
				
				# Update conference_id if not set
				if not meeting.google_conference_id:
					meeting.google_conference_id = conference_id
					updates.append("Conference ID")
				
				# Update start time
				start_time = conference.get('startTime')
				if start_time and not meeting.actual_start_time:
					meeting.actual_start_time = start_time
					updates.append("Start time")
				
				# Update end time and status
				end_time = conference.get('endTime')
				if end_time:
					if not meeting.actual_end_time:
						meeting.actual_end_time = end_time
						updates.append("End time")
					
					if meeting.status in ["Scheduled", "In Progress"]:
						meeting.status = "Completed"
						updates.append("Status → Completed")
				elif start_time and meeting.status == "Scheduled":
					meeting.status = "In Progress"
					updates.append("Status → In Progress")
				
				# Try to fetch transcript if meeting is completed
				if end_time and not meeting.transcript:
					try:
						transcripts_response = meet_service.conferenceRecords().transcripts().list(
							parent=conference.get('name')
						).execute()
						
						transcripts = transcripts_response.get('transcripts', [])
						
						if transcripts:
							transcript = transcripts[0]
							transcript_name = transcript.get('name')
							
							# List transcript entries
							entries_response = meet_service.conferenceRecords().transcripts().entries().list(
								parent=transcript_name
							).execute()
							
							entries = entries_response.get('entries', [])
							
							# Combine transcript text
							full_transcript = []
							for entry in entries:
								participant = entry.get('participant', '')
								text = entry.get('text', '')
								start_time_entry = entry.get('startTime', '')
								full_transcript.append(f"[{start_time_entry}] {participant}: {text}")
							
							meeting.transcript = "\n".join(full_transcript)
							meeting.transcript_retrieved_at = frappe.utils.now_datetime()
							meeting.status = "Transcript Retrieved"
							
							# Get Drive file info
							drive_destination = transcript.get('driveDestination', {})
							if drive_destination:
								file_id = drive_destination.get('file', '').split('/')[-1]
								meeting.transcript_file_id = file_id
								meeting.transcript_url = f"https://drive.google.com/file/d/{file_id}/view"
							
							updates.append("Transcript")
					except Exception as transcript_error:
						frappe.log_error(
							title=f"Transcript fetch failed during sync - {meeting_name}",
							message=str(transcript_error)
						)
						# Don't fail the whole sync if transcript fetch fails
				
				# Save updates
				meeting.save(ignore_permissions=True)
				frappe.db.commit()
				
				if updates:
					message = f"Updated: {', '.join(updates)}"
					frappe.msgprint(_(message), indicator="green")
					return {
						"success": True,
						"message": message,
						"updates": updates,
						"status": meeting.status
					}
				else:
					frappe.msgprint(_("Meeting is already up to date"), indicator="blue")
					return {
						"success": True,
						"message": "Already up to date",
						"updates": [],
						"status": meeting.status
					}
			else:
				frappe.msgprint(
					_("No conference found for this meeting. Meeting may not have been started yet."),
					indicator="orange"
				)
				return {
					"success": False,
					"message": "No conference found"
				}
				
		except Exception as api_error:
			frappe.log_error(
				title=f"Google Meet API error - {meeting_name}",
				message=str(api_error)
			)
			frappe.throw(_(f"Failed to fetch from Google Meet API: {str(api_error)}"))
			
	except Exception as e:
		frappe.log_error(
			title=f"Sync from Google Meet failed - {meeting_name}",
			message=str(e)
		)
		frappe.throw(_(f"Failed to sync from Google Meet: {str(e)}"))


@frappe.whitelist()
def fetch_transcript_manually(meeting_name):
	"""Manually fetch transcript for a completed meeting"""
	meeting = frappe.get_doc("VidCon Meeting", meeting_name)
	meeting.check_permission("write")
	
	# Validate meeting is completed
	if meeting.status not in ["Completed", "In Progress"]:
		frappe.throw(_("Meeting must be completed before fetching transcript"))
	
	# Check if we have conference_id (needed for Meet API)
	if not meeting.google_conference_id:
		frappe.throw(_("No conference ID found. Meeting may not have been started yet."))
	
	# Check if transcript already exists
	if meeting.transcript and meeting.status == "Transcript Retrieved":
		frappe.msgprint(_("Transcript already exists. Re-fetching..."), indicator="orange")
	
	try:
		# Import the transcript fetch function
		from vidcon.vidcon.doctype.vidcon_meeting.google_meet_events import fetch_transcript_for_conference
		
		# Fetch transcript synchronously
		fetch_transcript_for_conference(
			conference_id=meeting.google_conference_id,
			meeting_name=meeting.name
		)
		
		# Reload to get updated data
		meeting.reload()
		
		if meeting.transcript:
			frappe.msgprint(_("Transcript fetched successfully!"), indicator="green")
			return {
				"success": True,
				"message": "Transcript retrieved",
				"status": meeting.status,
				"transcript_length": len(meeting.transcript)
			}
		else:
			frappe.msgprint(_("No transcript found. Transcript may not be available yet."), indicator="orange")
			return {
				"success": False,
				"message": "No transcript available yet"
			}
			
	except Exception as e:
		frappe.log_error(
			title=f"Manual Transcript Fetch Failed - {meeting_name}",
			message=str(e)
		)
		frappe.throw(_(f"Failed to fetch transcript: {str(e)}"))
