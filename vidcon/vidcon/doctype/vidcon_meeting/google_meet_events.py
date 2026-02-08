import frappe
from frappe import _
import json
import base64


def log_event(event_type, event_id, subscription_id, event_data, raw_payload):
	"""
	Log incoming Pub/Sub event to VidCon Event Log for monitoring.
	"""
	try:
		print("\n" + "="*80)
		print("LOG_EVENT CALLED")
		print(f"event_type: {event_type}")
		print(f"event_type length: {len(event_type) if event_type else 0}")
		print(f"event_type type: {type(event_type)}")
		print(f"event_id: {event_id}")
		print(f"subscription_id: {subscription_id}")
		print("="*80 + "\n")
		
		# Extract space_id and conference_id from event data
		space_id = None
		conference_id = None
		meeting = None
		
		# Parse based on event structure
		if 'conferenceRecord' in event_data:
			conference_name = event_data['conferenceRecord'].get('name', '')
			if conference_name:
				conference_id = conference_name.split('/')[-1]
				print(f"Extracted conference_id: {conference_id}")
				# Try to find meeting by conference_id
				meetings = frappe.get_all(
					"VidCon Meeting",
					filters={"google_conference_id": conference_id},
					limit=1
				)
				if meetings:
					meeting = meetings[0].name
					print(f"Found meeting: {meeting}")
		
		elif 'participantSession' in event_data:
			session_name = event_data['participantSession'].get('name', '')
			if session_name:
				# Format: conferenceRecords/CONF_ID/participants/PART_ID/participantSessions/SESSION_ID
				parts = session_name.split('/')
				if len(parts) >= 2:
					conference_id = parts[1]
					print(f"Extracted conference_id from session: {conference_id}")
					# Try to find meeting by conference_id
					meetings = frappe.get_all(
						"VidCon Meeting",
						filters={"google_conference_id": conference_id},
						limit=1
					)
					if meetings:
						meeting = meetings[0].name
						print(f"Found meeting: {meeting}")
		
		print("\nCreating VidCon Event Log document...")
		print(f"  event_type: '{event_type}' (len={len(event_type) if event_type else 0})")
		print(f"  event_id: '{event_id}'")
		print(f"  subscription_id: '{subscription_id}'")
		print(f"  space_id: '{space_id}'")
		print(f"  conference_id: '{conference_id}'")
		print(f"  meeting: '{meeting}'")
		print(f"  raw_payload length: {len(raw_payload) if raw_payload else 0}")
		
		# Create event log
		log = frappe.get_doc({
			"doctype": "VidCon Event Log",
			"event_type": event_type,
			"event_id": event_id,
			"subscription_id": subscription_id,
			"received_at": frappe.utils.now(),
			"status": "Received",
			"space_id": space_id,
			"conference_id": conference_id,
			"meeting": meeting,
			"raw_payload": raw_payload
		})
		
		print("Document created, calling insert()...")
		log.insert(ignore_permissions=True)
		print(f"Insert successful! Log name: {log.name}")
		
		frappe.db.commit()
		print("Commit successful!")
		print("="*80 + "\n")
		
	except Exception as e:
		import traceback
		print("\n" + "!"*80)
		print("ERROR IN LOG_EVENT!")
		print(f"Exception type: {type(e).__name__}")
		print(f"Exception message: {str(e)}")
		print(f"\nFull traceback:")
		print(traceback.format_exc())
		print("!"*80 + "\n")
		
		error_details = {
			"error": str(e),
			"traceback": traceback.format_exc(),
			"event_type": event_type,
			"event_type_length": len(event_type) if event_type else 0,
			"event_id": event_id,
			"subscription_id": subscription_id
		}
		frappe.logger().error(f"Error logging event: {str(e)}")
		frappe.log_error(title="Event Logging Failed", message=frappe.as_json(error_details, indent=2))


@frappe.whitelist(allow_guest=True, methods=['POST'])
def handle_pubsub_push():
	"""
	Handle incoming Pub/Sub push notifications from Google Workspace Events.
	This is the webhook endpoint that receives Meet event notifications.
	
	Note: allow_guest=True is required for Pub/Sub push endpoint.
	Security is handled by validating the Pub/Sub token in the request.
	"""
	# TODO: Add Pub/Sub token validation for production
	# Validate the token from Pub/Sub subscription to ensure authenticity
	try:
		# Get the request data
		envelope = frappe.local.form_dict
		
		# Log raw incoming message
		print(f"\n{'='*80}")
		print(f"RAW INCOMING PUB/SUB MESSAGE")
		print(f"{'='*80}")
		print(json.dumps(envelope, indent=2))
		print(f"{'='*80}\n")
		
		# Get the Pub/Sub message from request
		envelope = frappe.request.get_json()
		
		if not envelope:
			frappe.logger().error("No Pub/Sub message received")
			return {"status": "error", "message": "No message"}
		
		# Extract the Pub/Sub message
		pubsub_message = envelope.get('message', {})
		
		if not pubsub_message:
			frappe.logger().error("Invalid Pub/Sub envelope")
			return {"status": "error", "message": "Invalid envelope"}
		
		# Decode the base64-encoded data
		data = pubsub_message.get('data', '')
		if data:
			decoded_data = base64.b64decode(data).decode('utf-8')
			event_data = json.loads(decoded_data)
		else:
			event_data = {}
		
		# Get attributes
		attributes = pubsub_message.get('attributes', {})
		
		# Debug logging
		print(f"\n=== Pub/Sub Message Received ===")
		print(f"Raw Envelope: {json.dumps(envelope, indent=2)}")
		print(f"\nAttributes: {json.dumps(attributes, indent=2)}")
		print(f"Event Data Keys: {list(event_data.keys())}")
		print(f"Event Data: {json.dumps(event_data, indent=2)}")
		
		# Extract event type - try multiple locations
		# CloudEvents format uses 'type' in attributes
		event_type = (
			attributes.get('ce-type', '') or  # CloudEvents type in attributes
			event_data.get('eventType', '') or  # eventType in data
			event_data.get('type', '') or  # type in data
			''
		)
		
		print(f"Extracted event_type: '{event_type}'")
		print(f"Event type length: {len(event_type)}")
		
		# Get event ID and subscription from attributes or data
		event_id = attributes.get('ce-id', pubsub_message.get('messageId', ''))
		subscription_id = envelope.get('subscription', '')
		
		print(f"\n{'='*80}")
		print(f"PROCESSING EVENT: {event_type}")
		print(f"{'='*80}")
		frappe.logger().info(f"Received Meet event: {event_type}")
		
		# Log the event to VidCon Event Log
		log_event(
			event_type=event_type,
			event_id=event_id,
			subscription_id=subscription_id,
			event_data=event_data,
			raw_payload=json.dumps(envelope, indent=2)
		)
		
		# Process the event based on type
		if event_type == 'google.workspace.meet.conference.v2.started':
			print(f"→ Calling handle_conference_started()")
			handle_conference_started(event_data)
		elif event_type == 'google.workspace.meet.conference.v2.ended':
			print(f"→ Calling handle_conference_ended()")
			handle_conference_ended(event_data)
		elif event_type == 'google.workspace.meet.participant.v2.joined':
			print(f"→ Calling handle_participant_joined()")
			handle_participant_joined(event_data)
		elif event_type == 'google.workspace.meet.participant.v2.left':
			print(f"→ Calling handle_participant_left()")
			handle_participant_left(event_data)
		elif event_type == 'google.workspace.meet.recording.v2.fileGenerated':
			print(f"→ Calling handle_recording_ready()")
			handle_recording_ready(event_data)
		elif event_type == 'google.workspace.meet.transcript.v2.fileGenerated':
			print(f"→ Calling handle_transcript_ready()")
			handle_transcript_ready(event_data)
		else:
			print(f"⚠ Unhandled event type: {event_type}")
			frappe.logger().info(f"Unhandled event type: {event_type}")
		
		print(f"{'='*80}\n")
		
		# Always return 200 to acknowledge receipt
		return {"status": "ok"}
		
	except Exception as e:
		frappe.logger().error(f"Error handling Pub/Sub message: {str(e)}")
		frappe.log_error(title="Pub/Sub Handler Error", message=str(e))
		# Return 200 to prevent Pub/Sub from retrying
		return {"status": "error", "message": str(e)}


def handle_conference_started(event_data):
	"""
	Handle conference.started event.
	Update VidCon Meeting status to In Progress.
	"""
	try:
		print(f"\n=== HANDLING CONFERENCE STARTED ===")
		print(f"Event data: {json.dumps(event_data, indent=2)}")
		
		# Extract conference details
		conference_record = event_data.get('conferenceRecord', {})
		conference_name = conference_record.get('name', '')
		conference_id = conference_name.split('/')[-1] if conference_name else ''
		start_time = conference_record.get('startTime')
		
		print(f"Conference ID: {conference_id}")
		print(f"Start time: {start_time}")
		
		# Find VidCon Meeting by conference ID or space ID
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={
				"google_conference_id": conference_id,
				"status": "Scheduled"
			},
			fields=["name", "google_space_id", "google_meet_link"]
		)
		
		print(f"Found {len(meetings)} meetings by conference_id")
		
		# If not found by conference ID, try by space ID from subscription
		if not meetings:
			# Get space ID from the event (it's in the ce-subject attribute)
			# We'll need to pass it from the main handler
			print(f"No meetings found by conference_id, trying all scheduled meetings")
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={"status": "Scheduled"},
				fields=["name", "google_space_id", "google_meet_link", "google_conference_id"]
			)
			print(f"All scheduled meetings: {json.dumps(meetings, indent=2)}")
		
		for meeting in meetings:
			meeting_doc = frappe.get_doc("VidCon Meeting", meeting.name)
			
			# Store conference ID if not already set
			if not meeting_doc.google_conference_id:
				meeting_doc.google_conference_id = conference_id
			
			meeting_doc.status = "In Progress"
			meeting_doc.actual_start_time = start_time
			meeting_doc.save(ignore_permissions=True)
			
			print(f"✓ Meeting {meeting.name} marked as In Progress")
			frappe.logger().info(f"Meeting {meeting.name} marked as In Progress")
		
		if not meetings:
			print(f"✗ No meetings found for conference {conference_id}")
		
		frappe.db.commit()
		print(f"=== CONFERENCE STARTED HANDLER COMPLETE ===\n")
		
	except Exception as e:
		print(f"✗ Error handling conference started: {str(e)}")
		frappe.logger().error(f"Error handling conference started: {str(e)}")
		frappe.log_error(title="Conference Started Handler Error", message=str(e))


def handle_participant_joined(event_data):
	"""
	Handle participant.joined event.
	Create or update attendee record.
	"""
	try:
		# Extract participant details
		participant_session = event_data.get('participantSession', {})
		session_name = participant_session.get('name', '')
		
		# Parse: conferenceRecords/CONF_ID/participants/PART_ID/participantSessions/SESSION_ID
		parts = session_name.split('/')
		if len(parts) >= 2:
			conference_id = parts[1]
			
			frappe.logger().info(f"Participant joined conference: {conference_id}")
			
			# TODO: Implement attendee tracking
			# - Find VidCon Meeting by conference_id
			# - Extract participant email/name from session data
			# - Create/update VidCon Meeting Attendee record
			# - Set joined_at timestamp
		
	except Exception as e:
		frappe.logger().error(f"Error handling participant joined: {str(e)}")
		frappe.log_error(title="Participant Joined Handler Error", message=str(e))


def handle_participant_left(event_data):
	"""
	Handle participant.left event.
	Update attendee record with left timestamp.
	"""
	try:
		# Extract participant details
		participant_session = event_data.get('participantSession', {})
		session_name = participant_session.get('name', '')
		
		# Parse: conferenceRecords/CONF_ID/participants/PART_ID/participantSessions/SESSION_ID
		parts = session_name.split('/')
		if len(parts) >= 2:
			conference_id = parts[1]
			
			frappe.logger().info(f"Participant left conference: {conference_id}")
			
			# TODO: Implement attendee tracking
			# - Find VidCon Meeting by conference_id
			# - Find attendee record by participant session
			# - Set left_at timestamp
		
	except Exception as e:
		frappe.logger().error(f"Error handling participant left: {str(e)}")
		frappe.log_error(title="Participant Left Handler Error", message=str(e))


def handle_conference_ended(event_data):
	"""
	Handle conference.ended event.
	Update VidCon Meeting status and trigger transcript fetch.
	"""
	try:
		print(f"\n=== HANDLING CONFERENCE ENDED ===")
		print(f"Event data: {json.dumps(event_data, indent=2)}")
		
		# Extract conference details
		conference_record = event_data.get('conferenceRecord', {})
		conference_name = conference_record.get('name', '')
		conference_id = conference_name.split('/')[-1] if conference_name else ''
		space_name = conference_record.get('space', '')
		end_time = conference_record.get('endTime')
		
		print(f"Conference ID: {conference_id}")
		print(f"End time: {end_time}")
		
		# Find VidCon Meeting by conference ID
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={
				"google_conference_id": conference_id,
				"status": ["in", ["Scheduled", "In Progress"]]
			},
			fields=["name", "google_meet_link", "google_conference_id"]
		)
		
		print(f"Found {len(meetings)} meetings by conference_id")
		
		# If not found, try all in-progress meetings
		if not meetings:
			print(f"No meetings found by conference_id, trying all in-progress meetings")
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={"status": ["in", ["Scheduled", "In Progress"]]},
				fields=["name", "google_meet_link", "google_conference_id"]
			)
			print(f"All in-progress meetings: {json.dumps(meetings, indent=2)}")
		
		for meeting in meetings:
			meeting_doc = frappe.get_doc("VidCon Meeting", meeting.name)
			
			# Store conference ID if not already set
			if not meeting_doc.google_conference_id:
				meeting_doc.google_conference_id = conference_id
			
			meeting_doc.status = "Completed"
			meeting_doc.actual_end_time = end_time
			meeting_doc.save(ignore_permissions=True)
			
			print(f"✓ Meeting {meeting.name} marked as Completed")
			frappe.logger().info(f"Meeting {meeting.name} marked as completed")
			
			# Enqueue transcript fetch after delay
			settings = frappe.get_single("VidCon Settings")
			delay_minutes = settings.transcript_fetch_delay or 10
			
			frappe.enqueue(
				"vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.fetch_transcript_for_conference",
				queue="default",
				timeout=600,
				conference_id=conference_id,
				meeting_name=meeting.name,
				enqueue_after_commit=True,
				# Schedule for later based on delay
				at_front=False
			)
			frappe.logger().info(f"Transcript fetch enqueued for {meeting.name} after {delay_minutes} minutes")
		
		frappe.db.commit()
		print(f"=== CONFERENCE ENDED HANDLER COMPLETE ===\n")
		
	except Exception as e:
		print(f"✗ Error handling conference ended: {str(e)}")
		frappe.logger().error(f"Error handling conference ended: {str(e)}")
		frappe.log_error(title="Conference Ended Handler Error", message=str(e))


def handle_recording_ready(event_data):
	"""
	Handle recording.fileGenerated event.
	Store recording details in VidCon Meeting.
	"""
	try:
		recording = event_data.get('recording', {})
		conference_id = recording.get('conferenceRecord', '').split('/')[-1]
		drive_file_id = recording.get('driveDestination', {}).get('file', '').split('/')[-1]
		
		frappe.logger().info(f"Recording ready for conference: {conference_id}")
		
		# Find VidCon Meeting
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={"google_meet_link": ["like", f"%{conference_id}%"]},
			fields=["name"]
		)
		
		for meeting in meetings:
			meeting_doc = frappe.get_doc("VidCon Meeting", meeting.name)
			
			# Store recording file ID (could add a field for this)
			frappe.logger().info(f"Recording available for {meeting.name}: {drive_file_id}")
			
			# TODO: Add recording_file_id field to VidCon Meeting if needed
			
		frappe.db.commit()
		
	except Exception as e:
		frappe.logger().error(f"Error handling recording ready: {str(e)}")


def handle_transcript_ready(event_data):
	"""
	Handle transcript.fileGenerated event.
	Get transcript details from Meet API and download from Drive.
	"""
	try:
		print(f"\n=== HANDLING TRANSCRIPT READY ===")
		print(f"Event data: {json.dumps(event_data, indent=2)}")
		
		transcript = event_data.get('transcript', {})
		transcript_name = transcript.get('name', '')
		
		print(f"Transcript name: {transcript_name}")
		frappe.logger().info(f"Transcript ready: {transcript_name}")
		
		# Extract conference ID from transcript name
		# Format: conferenceRecords/{conferenceId}/transcripts/{transcriptId}
		parts = transcript_name.split('/')
		if len(parts) >= 2:
			conference_id = parts[1]
		else:
			frappe.logger().error(f"Invalid transcript name format: {transcript_name}")
			return
		
		# Find VidCon Meeting by conference ID
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={"google_conference_id": conference_id},
			fields=["name"]
		)
		
		if not meetings:
			# Try finding by Meet link containing conference ID
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={"google_meet_link": ["like", f"%{conference_id}%"]},
				fields=["name"]
			)
		
		print(f"Found {len(meetings)} meetings")
		
		for meeting in meetings:
			print(f"Downloading transcript for meeting: {meeting.name}")
			# Get transcript details from Meet API and download
			download_transcript_from_meet_api(meeting.name, transcript_name)
		
		if not meetings:
			print(f"✗ No meetings found for conference {conference_id}")
		
		frappe.db.commit()
		print(f"=== TRANSCRIPT READY HANDLER COMPLETE ===\n")
		
	except Exception as e:
		print(f"✗ Error handling transcript ready: {str(e)}")
		frappe.logger().error(f"Error handling transcript ready: {str(e)}")
		frappe.log_error(title="Transcript Ready Handler Error", message=str(e))


def fetch_transcript_for_conference(conference_id, meeting_name):
	"""
	Fetch transcript from Google Drive using Meet API.
	Called after conference ends with a delay.
	"""
	try:
		meeting_doc = frappe.get_doc("VidCon Meeting", meeting_name)
		
		# Get Google Calendar credentials (we'll use same OAuth)
		settings = frappe.get_single("VidCon Settings")
		if not settings.google_calendar:
			frappe.logger().error("No Google Calendar configured")
			return
		
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		google_settings = frappe.get_single("Google Settings")
		
		# Build Meet API service
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
		from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import get_vidcon_access_token
		
		credentials = Credentials(
			token=get_vidcon_access_token(settings.google_calendar),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		# Use Meet API to list transcripts for this conference
		meet_service = build('meet', 'v2', credentials=credentials, static_discovery=False)
		
		# List transcripts for the conference
		conference_name = f"conferenceRecords/{conference_id}"
		
		try:
			transcripts_response = meet_service.conferenceRecords().transcripts().list(
				parent=conference_name
			).execute()
			
			transcripts = transcripts_response.get('transcripts', [])
			
			if transcripts:
				# Get the first transcript
				transcript = transcripts[0]
				transcript_name = transcript.get('name')
				
				# List transcript entries (the actual content)
				entries_response = meet_service.conferenceRecords().transcripts().entries().list(
					parent=transcript_name
				).execute()
				
				entries = entries_response.get('entries', [])
				
				# Combine all transcript text
				full_transcript = []
				for entry in entries:
					participant = entry.get('participant', '')
					text = entry.get('text', '')
					start_time = entry.get('startTime', '')
					
					full_transcript.append(f"[{start_time}] {participant}: {text}")
				
				# Store transcript
				meeting_doc.transcript = "\n".join(full_transcript)
				meeting_doc.transcript_retrieved_at = frappe.utils.now_datetime()
				meeting_doc.status = "Transcript Retrieved"
				
				# Get Drive file info if available
				drive_destination = transcript.get('driveDestination', {})
				if drive_destination:
					file_id = drive_destination.get('file', '').split('/')[-1]
					meeting_doc.transcript_file_id = file_id
					meeting_doc.transcript_url = f"https://drive.google.com/file/d/{file_id}/view"
				
				meeting_doc.save(ignore_permissions=True)
				frappe.db.commit()
				
				frappe.logger().info(f"Transcript saved for {meeting_name}")
			else:
				frappe.logger().info(f"No transcripts found yet for {conference_id}, will retry")
				
				# Retry after 5 minutes if no transcript found
				frappe.enqueue(
					"vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.fetch_transcript_for_conference",
					queue="default",
					timeout=600,
					conference_id=conference_id,
					meeting_name=meeting_name,
					enqueue_after_commit=True,
					at_front=False
				)
		
		except Exception as api_error:
			frappe.logger().error(f"Meet API error: {str(api_error)}")
			# Transcript might not be ready yet, retry
			frappe.enqueue(
				"vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.fetch_transcript_for_conference",
				queue="default",
				timeout=600,
				conference_id=conference_id,
				meeting_name=meeting_name,
				enqueue_after_commit=True,
				at_front=False
			)
	
	except Exception as e:
		frappe.logger().error(f"Error fetching transcript: {str(e)}")
		frappe.log_error(title="Transcript Fetch Error", message=str(e))


def download_transcript_from_meet_api(meeting_name, transcript_name):
	"""
	Get transcript details from Meet API and download from Drive.
	
	Args:
		meeting_name: VidCon Meeting name
		transcript_name: Full transcript resource name from Meet API
	"""
	try:
		meeting_doc = frappe.get_doc("VidCon Meeting", meeting_name)
		
		# Get credentials
		settings = frappe.get_single("VidCon Settings")
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		google_settings = frappe.get_single("Google Settings")
		
		# Build Meet API service
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
		from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import get_vidcon_access_token
		
		credentials = Credentials(
			token=get_vidcon_access_token(settings.google_calendar),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		meet_service = build('meet', 'v2', credentials=credentials, static_discovery=False)
		
		# Get transcript details from Meet API
		print(f"Getting transcript details: {transcript_name}")
		transcript_details = meet_service.conferenceRecords().transcripts().get(
			name=transcript_name
		).execute()
		
		print(f"Transcript details: {json.dumps(transcript_details, indent=2)}")
		
		# Extract Drive file ID from transcript details
		drive_destination = transcript_details.get('docsDestination', {})
		document_id = drive_destination.get('document', '').split('/')[-1]
		
		if not document_id:
			frappe.logger().error(f"No Drive document ID in transcript details: {transcript_details}")
			return
		
		print(f"Drive document ID: {document_id}")
		
		# Download transcript from Drive
		drive_service = build('drive', 'v3', credentials=credentials, static_discovery=False)
		
		# Export as plain text
		request = drive_service.files().export(
			fileId=document_id,
			mimeType='text/plain'
		)
		transcript_content = request.execute()
		
		# Store transcript
		meeting_doc.transcript = transcript_content.decode('utf-8') if isinstance(transcript_content, bytes) else transcript_content
		meeting_doc.transcript_file_id = document_id
		meeting_doc.transcript_url = f"https://docs.google.com/document/d/{document_id}/view"
		meeting_doc.transcript_retrieved_at = frappe.utils.now_datetime()
		meeting_doc.save(ignore_permissions=True)
		
		print(f"✓ Transcript downloaded and stored for {meeting_name}")
		frappe.logger().info(f"Transcript downloaded and stored for {meeting_name}")
		
	except Exception as e:
		frappe.logger().error(f"Error downloading transcript from Meet API: {str(e)}")
		frappe.log_error(title="Transcript Download Error", message=str(e))


def download_and_store_transcript(meeting_name, drive_file_id):
	"""
	Download transcript file from Google Drive and store in VidCon Meeting.
	"""
	try:
		meeting_doc = frappe.get_doc("VidCon Meeting", meeting_name)
		
		# Get Google Calendar credentials
		settings = frappe.get_single("VidCon Settings")
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		google_settings = frappe.get_single("Google Settings")
		
		# Build Drive service
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
		from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import get_vidcon_access_token
		
		credentials = Credentials(
			token=get_vidcon_access_token(settings.google_calendar),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		drive_service = build('drive', 'v3', credentials=credentials, static_discovery=False)
		
		# Download file content
		request = drive_service.files().get_media(fileId=drive_file_id)
		content = request.execute()
		
		# Store transcript
		meeting_doc.transcript = content.decode('utf-8') if isinstance(content, bytes) else content
		meeting_doc.transcript_file_id = drive_file_id
		meeting_doc.transcript_url = f"https://drive.google.com/file/d/{drive_file_id}/view"
		meeting_doc.transcript_retrieved_at = frappe.utils.now_datetime()
		meeting_doc.status = "Transcript Retrieved"
		meeting_doc.save(ignore_permissions=True)
		
		frappe.logger().info(f"Transcript downloaded and stored for {meeting_name}")
		
	except Exception as e:
		frappe.logger().error(f"Error downloading transcript: {str(e)}")
		frappe.log_error(title="Transcript Download Error", message=str(e))


def create_meet_subscription(user_email):
	"""
	Create a Google Workspace Events subscription for Meet conferences.
	This subscribes to conference.ended and transcript.ready events.
	"""
	try:
		settings = frappe.get_single("VidCon Settings")
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
		
		credentials = Credentials(
			token=google_calendar.get_password("access_token"),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_calendar.client_id,
			client_secret=google_calendar.get_password("client_secret")
		)
		
		# Build Workspace Events API service
		events_service = build('workspaceevents', 'v1', credentials=credentials, static_discovery=False)
		
		# Get Pub/Sub topic from settings
		pubsub_topic = settings.pubsub_topic_name  # e.g., "projects/PROJECT_ID/topics/meet-events"
		
		# Create subscription for conference ended events
		subscription_body = {
			"targetResource": f"//meet.googleapis.com/users/{user_email}",
			"eventTypes": [
				"google.workspace.meet.conference.v2.ended",
				"google.workspace.meet.transcript.v2.fileGenerated",
				"google.workspace.meet.recording.v2.fileGenerated"
			],
			"notificationEndpoint": {
				"pubsubTopic": pubsub_topic
			},
			"payloadOptions": {
				"includeResource": True
			}
		}
		
		response = events_service.subscriptions().create(body=subscription_body).execute()
		
		# Store subscription details
		settings.meet_subscription_id = response.get('name')
		settings.meet_subscription_state = response.get('state')
		settings.save(ignore_permissions=True)
		
		frappe.logger().info(f"Meet subscription created: {response.get('name')}")
		return response
		
	except Exception as e:
		frappe.logger().error(f"Error creating Meet subscription: {str(e)}")
		frappe.log_error(title="Meet Subscription Error", message=str(e))
		raise


def delete_meet_subscription(subscription_id):
	"""
	Delete a Google Workspace Events subscription.
	"""
	try:
		settings = frappe.get_single("VidCon Settings")
		google_calendar = frappe.get_doc("Google Calendar", settings.google_calendar)
		
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build
		
		credentials = Credentials(
			token=google_calendar.get_password("access_token"),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_calendar.client_id,
			client_secret=google_calendar.get_password("client_secret")
		)
		
		events_service = build('workspaceevents', 'v1', credentials=credentials, static_discovery=False)
		
		events_service.subscriptions().delete(name=subscription_id).execute()
		
		frappe.logger().info(f"Meet subscription deleted: {subscription_id}")
		
	except Exception as e:
		frappe.logger().error(f"Error deleting Meet subscription: {str(e)}")
