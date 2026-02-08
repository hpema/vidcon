import frappe
from frappe import _
import json
import hmac
import hashlib

@frappe.whitelist(allow_guest=True)
def handle_calendar_notification():
	"""
	Webhook endpoint for Google Calendar push notifications.
	Google will send notifications when calendar events change.
	
	Endpoint: /api/method/vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.handle_calendar_notification
	"""
	try:
		# Get the notification headers
		channel_id = frappe.request.headers.get("X-Goog-Channel-ID")
		resource_id = frappe.request.headers.get("X-Goog-Resource-ID")
		resource_state = frappe.request.headers.get("X-Goog-Resource-State")
		resource_uri = frappe.request.headers.get("X-Goog-Resource-URI")
		
		# Log the notification
		frappe.logger().info(f"Calendar notification received: {resource_state} for channel {channel_id}")
		
		# Handle sync (initial notification) vs exists (change notification)
		if resource_state == "sync":
			# Initial sync notification - just acknowledge
			frappe.logger().info("Calendar watch channel established")
			return {"status": "ok", "message": "Sync acknowledged"}
		
		elif resource_state == "exists":
			# Event changed - fetch updated event and check if it's a VidCon meeting
			frappe.enqueue(
				"vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.process_calendar_change",
				queue="default",
				timeout=300,
				channel_id=channel_id,
				resource_uri=resource_uri
			)
			
			return {"status": "ok", "message": "Processing change"}
		
		return {"status": "ok"}
		
	except Exception as e:
		frappe.logger().error(f"Error handling calendar notification: {str(e)}")
		# Return 200 to prevent Google from retrying
		return {"status": "error", "message": str(e)}


def process_calendar_change(channel_id, resource_uri):
	"""
	Process calendar change notification.
	Fetch the changed events and update VidCon meetings accordingly.
	"""
	try:
		# Get the Google Calendar associated with this channel
		settings = frappe.get_single("VidCon Settings")
		
		if not settings.google_calendar:
			frappe.logger().error("No Google Calendar configured in VidCon Settings")
			return
		
		# Get the Google Calendar service
		from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		service = get_google_calendar_object(google_calendar)
		
		# Fetch recent events (last hour)
		from datetime import datetime, timedelta
		time_min = (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'
		
		events_result = service.events().list(
			calendarId='primary',
			timeMin=time_min,
			maxResults=50,
			singleEvents=True,
			orderBy='startTime'
		).execute()
		
		events = events_result.get('items', [])
		
		# Check each event to see if it's linked to a VidCon meeting
		for event in events:
			event_id = event.get('id')
			
			# Find VidCon meetings linked to this event
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={"google_calendar_event_id": event_id},
				fields=["name", "status", "google_meet_link"]
			)
			
			for meeting in meetings:
				update_meeting_from_event(meeting.name, event)
		
		frappe.db.commit()
		
	except Exception as e:
		frappe.logger().error(f"Error processing calendar change: {str(e)}")
		frappe.log_error(title="Calendar Webhook Error", message=str(e))


def update_meeting_from_event(meeting_name, event):
	"""
	Update VidCon meeting based on Google Calendar event data.
	Check if meeting has ended and trigger transcript retrieval.
	"""
	try:
		meeting = frappe.get_doc("VidCon Meeting", meeting_name)
		
		# Update Google Meet link if not already set
		hangout_link = event.get('hangoutLink')
		if hangout_link and not meeting.google_meet_link:
			meeting.google_meet_link = hangout_link
			meeting.save(ignore_permissions=True)
			frappe.logger().info(f"Updated Meet link for {meeting_name}")
		
		# Check if meeting has ended
		event_status = event.get('status')
		end_time = event.get('end', {}).get('dateTime')
		
		if end_time:
			from frappe.utils import now_datetime, get_datetime
			end_datetime = get_datetime(end_time)
			
			# If meeting ended and status is still Scheduled, mark as Completed
			if end_datetime < now_datetime() and meeting.status == "Scheduled":
				meeting.status = "Completed"
				meeting.save(ignore_permissions=True)
				frappe.logger().info(f"Meeting {meeting_name} marked as completed")
				
				# Trigger transcript retrieval
				frappe.enqueue(
					"vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.fetch_meeting_transcript",
					queue="default",
					timeout=600,
					meeting_name=meeting_name,
					enqueue_after_commit=True
				)
		
	except Exception as e:
		frappe.logger().error(f"Error updating meeting {meeting_name}: {str(e)}")


def fetch_meeting_transcript(meeting_name):
	"""
	Fetch transcript from Google Drive after meeting completion.
	Transcripts are typically available 10-15 minutes after meeting ends.
	"""
	try:
		meeting = frappe.get_doc("VidCon Meeting", meeting_name)
		
		if not meeting.google_meet_link:
			frappe.logger().error(f"No Meet link for {meeting_name}")
			return
		
		# Extract meeting code from Meet link
		# Format: https://meet.google.com/abc-defg-hij
		meet_code = meeting.google_meet_link.split('/')[-1]
		
		# Get Google Drive service
		settings = frappe.get_single("VidCon Settings")
		if not settings.google_calendar:
			return
		
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		
		# Build Drive service using same credentials
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
		
		credentials = Credentials(
			token=google_calendar.get_password("access_token"),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_calendar.client_id,
			client_secret=google_calendar.get_password("client_secret")
		)
		
		drive_service = build('drive', 'v3', credentials=credentials, static_discovery=False)
		
		# Search for transcript file
		# Google Meet transcripts are typically named: "Meet Recording - [Title] - [Date].txt"
		# or stored in a specific folder
		query = f"name contains '{meet_code}' and mimeType='text/plain'"
		
		results = drive_service.files().list(
			q=query,
			spaces='drive',
			fields='files(id, name, createdTime, webViewLink)',
			orderBy='createdTime desc'
		).execute()
		
		files = results.get('files', [])
		
		if files:
			# Found transcript file(s)
			for file in files:
				# Download transcript content
				file_id = file['id']
				content = drive_service.files().get_media(fileId=file_id).execute()
				
				# Store transcript in VidCon Meeting
				meeting.transcript = content.decode('utf-8') if isinstance(content, bytes) else content
				meeting.transcript_file_id = file_id
				meeting.transcript_url = file.get('webViewLink')
				meeting.save(ignore_permissions=True)
				
				frappe.logger().info(f"Transcript saved for {meeting_name}")
				break
		else:
			# Transcript not found yet - retry after delay
			frappe.logger().info(f"Transcript not found for {meeting_name}, will retry")
			# Retry after 5 minutes
			frappe.enqueue(
				"vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.fetch_meeting_transcript",
				queue="default",
				timeout=600,
				meeting_name=meeting_name,
				enqueue_after_commit=True,
				at_front=False,
				now=False
			)
	
	except Exception as e:
		frappe.logger().error(f"Error fetching transcript for {meeting_name}: {str(e)}")
		frappe.log_error(title="Transcript Fetch Error", message=str(e))


def setup_calendar_watch(google_calendar_name):
	"""
	Setup Google Calendar push notifications (watch).
	This needs to be called to start receiving notifications.
	"""
	try:
		from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
		import uuid
		from datetime import datetime, timedelta
		
		google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
		service = get_google_calendar_object(google_calendar)
		
		# Generate unique channel ID
		channel_id = str(uuid.uuid4())
		
		# Get webhook URL
		settings = frappe.get_single("VidCon Settings")
		webhook_url = f"{frappe.utils.get_url()}/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.handle_calendar_notification"
		
		# Setup watch (expires after 7 days, max allowed by Google)
		expiration = int((datetime.utcnow() + timedelta(days=7)).timestamp() * 1000)
		
		body = {
			'id': channel_id,
			'type': 'web_hook',
			'address': webhook_url,
			'expiration': expiration
		}
		
		response = service.events().watch(calendarId='primary', body=body).execute()
		
		# Store channel info for renewal
		settings.calendar_watch_channel_id = channel_id
		settings.calendar_watch_resource_id = response.get('resourceId')
		settings.calendar_watch_expiration = datetime.fromtimestamp(expiration / 1000)
		settings.save(ignore_permissions=True)
		
		frappe.logger().info(f"Calendar watch setup: {channel_id}")
		return response
		
	except Exception as e:
		frappe.logger().error(f"Error setting up calendar watch: {str(e)}")
		frappe.log_error(title="Calendar Watch Setup Error", message=str(e))
		raise


def stop_calendar_watch(channel_id, resource_id, google_calendar_name):
	"""
	Stop Google Calendar push notifications.
	"""
	try:
		from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
		
		google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
		service = get_google_calendar_object(google_calendar)
		
		body = {
			'id': channel_id,
			'resourceId': resource_id
		}
		
		service.channels().stop(body=body).execute()
		frappe.logger().info(f"Calendar watch stopped: {channel_id}")
		
	except Exception as e:
		frappe.logger().error(f"Error stopping calendar watch: {str(e)}")
