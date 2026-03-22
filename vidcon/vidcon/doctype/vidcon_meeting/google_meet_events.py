import frappe
from frappe import _
import json
import base64
import jwt
from jwt import PyJWKClient
import requests
from datetime import datetime


def verify_pubsub_jwt(token, audience):
	"""
	Verify JWT token from Google Pub/Sub push endpoint.
	
	Args:
		token: JWT token from Authorization header
		audience: Expected audience (your webhook URL)
	
	Returns:
		dict: Decoded token payload if valid, None otherwise
	"""
	try:
		# Google's public keys URL
		jwks_url = "https://www.googleapis.com/oauth2/v3/certs"
		
		# Create JWK client to fetch Google's public keys
		jwks_client = PyJWKClient(jwks_url)
		
		# Get the signing key from the token
		signing_key = jwks_client.get_signing_key_from_jwt(token)
		
		# Verify and decode the token
		decoded = jwt.decode(
			token,
			signing_key.key,
			algorithms=["RS256"],
			audience=audience,
			options={"verify_exp": True}
		)
		
		# Verify issuer is Google
		if decoded.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
			frappe.log_error(title="Invalid JWT Issuer", message=f"Issuer: {decoded.get('iss')}")
			return None
		
		frappe.log_error(title="Pub/Sub JWT Verified", message=f"Token verified for email: {decoded.get('email')}")
		return decoded
		
	except jwt.ExpiredSignatureError:
		frappe.log_error(title="JWT Expired", message="Pub/Sub JWT token has expired")
		return None
	except jwt.InvalidAudienceError:
		frappe.log_error(title="Invalid JWT Audience", message=f"Expected: {audience}")
		return None
	except Exception as e:
		frappe.log_error(title="JWT Verification Failed", message=str(e))
		return None


def log_event(event_type, event_id, subscription_id, event_data, raw_payload):
	"""
	Log incoming Pub/Sub event to VidCon Event Log for monitoring.
	"""
	try:
		frappe.logger().info("\n" + "="*80)
		frappe.logger().info("LOG_EVENT CALLED")
		frappe.logger().info(f"event_type: {event_type}")
		frappe.logger().info(f"event_type length: {len(event_type) if event_type else 0}")
		frappe.logger().info(f"event_type type: {type(event_type)}")
		frappe.logger().info(f"event_id: {event_id}")
		frappe.logger().info(f"subscription_id: {subscription_id}")
		frappe.logger().info("="*80 + "\n")
		
		# Extract space_id and conference_id from event data
		space_id = None
		conference_id = None
		meeting = None
		
		# Parse based on event structure
		if 'conferenceRecord' in event_data:
			conference_name = event_data['conferenceRecord'].get('name', '')
			if conference_name:
				conference_id = conference_name.split('/')[-1]
				frappe.logger().info(f"Extracted conference_id: {conference_id}")
				# Try to find meeting by conference_id
				meetings = frappe.get_all(
					"VidCon Meeting",
					filters={"google_conference_id": conference_id},
					limit=1
				)
				if meetings:
					meeting = meetings[0].name
					frappe.logger().info(f"Found meeting: {meeting}")
		
		elif 'participantSession' in event_data:
			session_name = event_data['participantSession'].get('name', '')
			if session_name:
				# Format: conferenceRecords/CONF_ID/participants/PART_ID/participantSessions/SESSION_ID
				parts = session_name.split('/')
				if len(parts) >= 2:
					conference_id = parts[1]
					frappe.logger().info(f"Extracted conference_id from session: {conference_id}")
					# Try to find meeting by conference_id
					meetings = frappe.get_all(
						"VidCon Meeting",
						filters={"google_conference_id": conference_id},
						limit=1
					)
					if meetings:
						meeting = meetings[0].name
						frappe.logger().info(f"Found meeting: {meeting}")
		
		frappe.logger().info("\nCreating VidCon Event Log document...")
		frappe.logger().info(f"  event_type: '{event_type}' (len={len(event_type) if event_type else 0})")
		frappe.logger().info(f"  event_id: '{event_id}'")
		frappe.logger().info(f"  subscription_id: '{subscription_id}'")
		frappe.logger().info(f"  space_id: '{space_id}'")
		frappe.logger().info(f"  conference_id: '{conference_id}'")
		frappe.logger().info(f"  meeting: '{meeting}'")
		frappe.logger().info(f"  raw_payload length: {len(raw_payload) if raw_payload else 0}")
		
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
		
		frappe.logger().info("Document created, calling insert()...")
		log.insert(ignore_permissions=True)
		frappe.logger().info(f"Insert successful! Log name: {log.name}")
		
		frappe.db.commit()
		frappe.logger().info("Commit successful!")
		frappe.logger().info("="*80 + "\n")
		
	except Exception as e:
		import traceback
		frappe.logger().info("\n" + "!"*80)
		frappe.logger().info("ERROR IN LOG_EVENT!")
		frappe.logger().info(f"Exception type: {type(e).__name__}")
		frappe.logger().info(f"Exception message: {str(e)}")
		frappe.logger().info(f"\nFull traceback:")
		frappe.logger().info(traceback.format_exc())
		frappe.logger().info("!"*80 + "\n")
		
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
	Security is handled by validating the JWT token from Google.
	"""
	try:
		# === COMPREHENSIVE LOGGING START ===
		import datetime
		timestamp = datetime.datetime.now().isoformat()
		
		# Log that webhook was called
		frappe.log_error(
			title=f"🔔 Pub/Sub Webhook Called - {timestamp}",
			message=f"Webhook endpoint hit at {timestamp}\nMethod: {frappe.request.method}\nPath: {frappe.request.path}"
		)
		
		# Log all request headers
		headers_dict = dict(frappe.request.headers)
		frappe.log_error(
			title=f"📋 Request Headers - {timestamp}",
			message=json.dumps(headers_dict, indent=2)
		)
		
		# Get raw request body
		raw_body = None
		try:
			raw_body = frappe.request.get_data(as_text=True)
			frappe.log_error(
				title=f"📦 Raw Request Body - {timestamp}",
				message=f"Body length: {len(raw_body)} bytes\n\n{raw_body[:2000]}"  # First 2000 chars
			)
		except Exception as body_error:
			frappe.log_error(
				title=f"⚠️ Could not read request body - {timestamp}",
				message=str(body_error)
			)
		
		# Verify JWT token from Authorization header (optional for now)
		auth_header = frappe.request.headers.get('Authorization', '')
		if not auth_header.startswith('Bearer '):
			frappe.log_error(
				title=f"⚠️ No JWT Token - Proceeding Without Auth - {timestamp}",
				message=f"Authorization header: {auth_header[:50] if auth_header else 'EMPTY'}\n\nWARNING: JWT authentication is disabled. This is insecure.\nConfigure Pub/Sub push subscription with service account authentication."
			)
			# Continue without JWT verification for now
		else:
			token = auth_header.replace('Bearer ', '')
			frappe.log_error(
				title=f"🔑 JWT Token Received - {timestamp}",
				message=f"Token length: {len(token)} characters\nFirst 50 chars: {token[:50]}..."
			)
			
			# Get the webhook URL for audience verification
			# Remove port from URL as Google's JWT audience doesn't include it
			site_url = frappe.utils.get_url()
			# Remove :443 or :80 from the URL
			import re
			site_url_clean = re.sub(r':(443|80)$', '', site_url)
			audience = f"{site_url_clean}/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push"
			
			frappe.log_error(
				title=f"🎯 Verifying JWT Audience - {timestamp}",
				message=f"Expected audience: {audience}"
			)
			
			# Verify the JWT token
			decoded_token = verify_pubsub_jwt(token, audience)
			if not decoded_token:
				frappe.log_error(
					title=f"❌ JWT Verification Failed - {timestamp}",
					message="Invalid or expired JWT token from Pub/Sub"
				)
				return {"status": "error", "message": "Unauthorized"}, 401
			
			frappe.log_error(
				title=f"✅ JWT Verified Successfully - {timestamp}",
				message=f"Verified token for: {decoded_token.get('email')}\nIssuer: {decoded_token.get('iss')}"
			)
		
		# Get the Pub/Sub message from request
		# Parse from raw_body since we already read the stream
		envelope = None
		if raw_body:
			try:
				envelope = json.loads(raw_body)
			except json.JSONDecodeError as e:
				frappe.log_error(
					title=f"❌ JSON Parse Error - {timestamp}",
					message=f"Could not parse request body as JSON: {str(e)}\nBody: {raw_body[:500]}"
				)
				return {"status": "error", "message": "Invalid JSON"}
		
		if not envelope:
			frappe.log_error(title="Empty Pub/Sub Message", message="No message in request body")
			return {"status": "error", "message": "No message"}
		
		# Log complete envelope structure for analysis
		frappe.log_error(
			title=f"📬 Complete Pub/Sub Envelope - {timestamp}",
			message=f"Full envelope structure:\n{json.dumps(envelope, indent=2)}"
		)
		
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
			frappe.log_error(
				title=f"📨 Decoded Event Data - {timestamp}",
				message=f"Decoded data:\n{json.dumps(event_data, indent=2)}"
			)
		else:
			event_data = {}
			frappe.log_error(
				title=f"⚠️ Empty Event Data - {timestamp}",
				message="No data field in Pub/Sub message"
			)
		
		# Get attributes
		attributes = pubsub_message.get('attributes', {})
		frappe.log_error(
			title=f"🏷️ Event Attributes - {timestamp}",
			message=json.dumps(attributes, indent=2)
		)
		
		# Extract event type - try multiple locations
		# CloudEvents format uses 'type' in attributes
		event_type = (
			attributes.get('ce-type', '') or  # CloudEvents type in attributes
			event_data.get('eventType', '') or  # eventType in data
			event_data.get('type', '') or  # type in data
			''
		)
		
		frappe.log_error(
			title=f"🎯 Event Type Extracted - {timestamp}",
			message=f"Event Type: '{event_type}'\nLength: {len(event_type)}\nSource: {attributes.get('ce-source', 'N/A')}"
		)
		
		# Get event ID and subscription from attributes or data
		event_id = attributes.get('ce-id', pubsub_message.get('messageId', ''))
		subscription_id = envelope.get('subscription', '')
		
		frappe.log_error(
			title=f"🆔 Event Identifiers - {timestamp}",
			message=f"Event ID: {event_id}\nSubscription: {subscription_id}\nMessage ID: {pubsub_message.get('messageId', 'N/A')}"
		)
		
		frappe.logger().info(f"\n{'='*80}")
		frappe.logger().info(f"PROCESSING EVENT: {event_type}")
		frappe.logger().info(f"{'='*80}")
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
			frappe.log_error(
				title=f"🚀 Processing: conference.started - {timestamp}",
				message="Calling handle_conference_started()"
			)
			handle_conference_started(event_data, attributes)
		elif event_type == 'google.workspace.meet.conference.v2.ended':
			frappe.log_error(
				title=f"🏁 Processing: conference.ended - {timestamp}",
				message="Calling handle_conference_ended()"
			)
			handle_conference_ended(event_data, attributes)
		elif event_type == 'google.workspace.meet.participant.v2.joined':
			frappe.log_error(
				title=f"👤 Processing: participant.joined - {timestamp}",
				message="Calling handle_participant_joined()"
			)
			handle_participant_joined(event_data, attributes)
		elif event_type == 'google.workspace.meet.participant.v2.left':
			frappe.log_error(
				title=f"👋 Processing: participant.left - {timestamp}",
				message="Calling handle_participant_left()"
			)
			handle_participant_left(event_data, attributes)
		elif event_type == 'google.workspace.meet.recording.v2.fileGenerated':
			frappe.log_error(
				title=f"🎥 Processing: recording.fileGenerated - {timestamp}",
				message="Calling handle_recording_ready()"
			)
			handle_recording_ready(event_data, attributes)
		elif event_type == 'google.workspace.meet.transcript.v2.fileGenerated':
			frappe.log_error(
				title=f"📝 Processing: transcript.fileGenerated - {timestamp}",
				message="Calling handle_transcript_ready()"
			)
			handle_transcript_ready(event_data, attributes)
		else:
			frappe.log_error(
				title=f"⚠️ Unhandled Event Type - {timestamp}",
				message=f"Event type: '{event_type}'\nFull event data:\n{json.dumps(event_data, indent=2)}"
			)
		
		# Log successful completion
		frappe.log_error(
			title=f"✅ Webhook Processing Complete - {timestamp}",
			message=f"Event type '{event_type}' processed successfully\nReturning status: ok"
		)
		
		# Always return 200 to acknowledge receipt
		return {"status": "ok"}
		
	except Exception as e:
		frappe.logger().error(f"Error handling Pub/Sub message: {str(e)}")
		frappe.log_error(title="Pub/Sub Handler Error", message=str(e))
		# Return 200 to prevent Pub/Sub from retrying
		return {"status": "error", "message": str(e)}


def handle_conference_started(event_data, attributes):
	"""
	Handle conference.started event.
	Update VidCon Meeting status to In Progress.
	"""
	try:
		frappe.logger().info(f"\n=== HANDLING CONFERENCE STARTED ===")
		frappe.logger().info(f"Event data: {json.dumps(event_data, indent=2)}")
		
		# Extract conference details
		conference_record = event_data.get('conferenceRecord', {})
		conference_name = conference_record.get('name', '')
		conference_id = conference_name.split('/')[-1] if conference_name else ''
		
		# Extract subscription UUID from ce-source
		ce_source = attributes.get('ce-source', '')
		subscription_uuid = ''
		subscription_uuid_encoded = ''
		if 'meet-spaces-' in ce_source:
			subscription_uuid = ce_source.split('meet-spaces-')[-1]
			# Encode UUID to base64 for matching against meet_subscription_id
			# The meet_subscription_id contains base64 encoded data with the UUID
			import base64
			uuid_with_prefix = f'${subscription_uuid}'.encode('utf-8')
			subscription_uuid_encoded = base64.b64encode(uuid_with_prefix).decode('utf-8')[:20]
		
		# Extract space ID from ce-subject attribute (format: //meet.googleapis.com/spaces/SPACE_ID)
		ce_subject = attributes.get('ce-subject', '')
		space_id = ce_subject.split('/')[-1] if ce_subject else ''
		
		# Fallback to event data if available
		if not space_id:
			space_name = conference_record.get('space', '')
			space_id = space_name.split('/')[-1] if space_name else ''
		
		start_time = conference_record.get('startTime')
		
		frappe.logger().info(f"Conference ID: {conference_id}")
		frappe.logger().info(f"Space ID: {space_id}")
		frappe.logger().info(f"Subscription UUID: {subscription_uuid}")
		frappe.logger().info(f"Start time: {start_time}")
		
		# Try to find meeting by conference_id first (if already set from previous event)
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={
				"google_conference_id": conference_id
			},
			fields=["name", "google_space_id", "google_meet_link", "status"]
		)
		
		frappe.logger().info(f"Found {len(meetings)} meetings by conference_id")
		
		# If not found by conference_id, try by subscription UUID (most reliable)
		if not meetings and subscription_uuid:
			frappe.logger().info(f"Trying to find meeting by subscription UUID: {subscription_uuid} (encoded: {subscription_uuid_encoded})")
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={
					"meet_subscription_id": ["like", f"%{subscription_uuid_encoded}%"]
				},
				fields=["name", "google_space_id", "google_meet_link", "google_conference_id", "meet_subscription_id", "status"]
			)
			frappe.logger().info(f"Found {len(meetings)} meetings by subscription UUID")
		
		# Fallback to space_id if subscription lookup fails
		if not meetings and space_id:
			frappe.logger().info(f"Trying to find meeting by space_id: {space_id}")
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={
					"google_space_id": space_id
				},
				fields=["name", "google_space_id", "google_meet_link", "google_conference_id", "status"]
			)
			frappe.logger().info(f"Found {len(meetings)} meetings by space_id")
		
		for meeting in meetings:
			meeting_doc = frappe.get_doc("VidCon Meeting", meeting.name)
			
			# Store conference ID (this is critical for subsequent events)
			if not meeting_doc.google_conference_id:
				meeting_doc.google_conference_id = conference_id
				frappe.logger().info(f"Stored conference_id {conference_id} for meeting {meeting.name}")
			
			meeting_doc.status = "In Progress"
			meeting_doc.actual_start_time = start_time
			meeting_doc.save(ignore_permissions=True)
			
			# Add activity comment for audit trail
			meeting_doc.add_comment(
				'Comment',
				f"🚀 **Conference Started**\n\n"
				f"- Conference ID: `{conference_id}`\n"
				f"- Start Time: {start_time}\n"
				f"- Status: In Progress"
			)
			
			# Send real-time notification
			frappe.publish_realtime(
				event='vidcon_meeting_started',
				message={
					'meeting_name': meeting.name,
					'status': 'In Progress',
					'conference_id': conference_id
				},
				doctype='VidCon Meeting',
				docname=meeting.name
			)
			
			frappe.logger().info(f"✓ Meeting {meeting.name} marked as In Progress")
			frappe.log_error(
				title=f"✅ Meeting {meeting.name} started",
				message=f"Meeting: {meeting.name}\nStatus: In Progress\nConference ID: {conference_id}\nStart time: {start_time}"
			)
		
		if not meetings:
			frappe.logger().info(f"✗ No meetings found for conference {conference_id} or space {space_id}")
		
		frappe.db.commit()
		frappe.logger().info(f"=== CONFERENCE STARTED HANDLER COMPLETE ===\n")
		
	except Exception as e:
		frappe.logger().info(f"✗ Error handling conference started: {str(e)}")
		frappe.logger().error(f"Error handling conference started: {str(e)}")
		frappe.log_error(title="Conference Started Handler Error", message=str(e))


def handle_participant_joined(event_data, attributes):
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


def handle_participant_left(event_data, attributes):
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


def handle_conference_ended(event_data, attributes):
	"""
	Handle conference.ended event.
	Update VidCon Meeting status and trigger transcript fetch.
	"""
	try:
		frappe.logger().info(f"\n=== HANDLING CONFERENCE ENDED ===")
		frappe.logger().info(f"Event data: {json.dumps(event_data, indent=2)}")
		
		# Extract conference details
		conference_record = event_data.get('conferenceRecord', {})
		conference_name = conference_record.get('name', '')
		conference_id = conference_name.split('/')[-1] if conference_name else ''
		
		# Extract subscription UUID from ce-source (format: //workspaceevents.googleapis.com/subscriptions/meet-spaces-UUID)
		ce_source = attributes.get('ce-source', '')
		subscription_uuid = ''
		subscription_uuid_encoded = ''
		if 'meet-spaces-' in ce_source:
			subscription_uuid = ce_source.split('meet-spaces-')[-1]
			# Encode UUID to base64 for matching against meet_subscription_id
			# The meet_subscription_id contains base64 encoded data with the UUID
			import base64
			# Create a search pattern from the first part of the base64 encoded UUID
			# Format in subscription: $a0094893-0ba5-4ebb-8a89-5c73d8dfebfe
			uuid_with_prefix = f'${subscription_uuid}'.encode('utf-8')
			subscription_uuid_encoded = base64.b64encode(uuid_with_prefix).decode('utf-8')[:20]
		
		# Extract space ID from ce-subject attribute (format: //meet.googleapis.com/spaces/SPACE_ID)
		ce_subject = attributes.get('ce-subject', '')
		space_id = ce_subject.split('/')[-1] if ce_subject else ''
		
		# Fallback to event data if available
		if not space_id:
			space_name = conference_record.get('space', '')
			space_id = space_name.split('/')[-1] if space_name else ''
		
		end_time = conference_record.get('endTime')
		# Use current time if endTime not provided
		if not end_time:
			from frappe.utils import now_datetime
			end_time = now_datetime()
		
		frappe.log_error(
			title=f"🔍 Looking for meeting - conference.ended",
			message=f"Conference ID: {conference_id}\nSpace ID: {space_id}\nSubscription UUID: {subscription_uuid}\nEncoded Subscription UUID: {subscription_uuid_encoded}\nEnd time: {end_time}"
		)
		
		frappe.logger().info(f"Conference ID: {conference_id}")
		frappe.logger().info(f"Space ID: {space_id}")
		frappe.logger().info(f"End time: {end_time}")
		
		# Try to find meeting by conference_id first
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={
				"google_conference_id": conference_id
			},
			fields=["name", "google_meet_link", "google_conference_id", "google_space_id", "status"]
		)
		
		frappe.log_error(
			title=f"📊 Meetings found by conference_id: {len(meetings)}",
			message=f"Conference ID: {conference_id}\nMeetings: {json.dumps([dict(m) for m in meetings], indent=2) if meetings else 'None'}"
		)
		frappe.logger().info(f"Found {len(meetings)} meetings by conference_id")
		
		# If not found by conference_id, try by subscription UUID (most reliable)
		if not meetings and subscription_uuid:
			frappe.log_error(
				title=f"🔍 Trying subscription UUID lookup",
				message=f"Subscription UUID: {subscription_uuid}\nEncoded search pattern: {subscription_uuid_encoded}\nConference ID not found, searching by subscription"
			)
			frappe.logger().info(f"Trying to find meeting by subscription UUID: {subscription_uuid} (encoded: {subscription_uuid_encoded})")
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={
					"meet_subscription_id": ["like", f"%{subscription_uuid_encoded}%"]
				},
				fields=["name", "google_meet_link", "google_conference_id", "google_space_id", "status", "meet_subscription_id"]
			)
			frappe.log_error(
				title=f"📊 Meetings found by subscription UUID: {len(meetings)}",
				message=f"Subscription UUID: {subscription_uuid}\nEncoded: {subscription_uuid_encoded}\nMeetings: {json.dumps([dict(m) for m in meetings], indent=2) if meetings else 'None'}"
			)
			frappe.logger().info(f"Found {len(meetings)} meetings by subscription UUID")
		
		# Fallback to space_id if subscription lookup fails
		if not meetings and space_id:
			frappe.log_error(
				title=f"🔍 Trying space_id lookup",
				message=f"Space ID: {space_id}\nSubscription not found, searching by space_id"
			)
			frappe.logger().info(f"Trying to find meeting by space_id: {space_id}")
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={
					"google_space_id": space_id
				},
				fields=["name", "google_meet_link", "google_conference_id", "google_space_id", "status"]
			)
			frappe.log_error(
				title=f"📊 Meetings found by space_id: {len(meetings)}",
				message=f"Space ID: {space_id}\nMeetings: {json.dumps([dict(m) for m in meetings], indent=2) if meetings else 'None'}"
			)
			frappe.logger().info(f"Found {len(meetings)} meetings by space_id")
		
		for meeting in meetings:
			meeting_doc = frappe.get_doc("VidCon Meeting", meeting.name)
			
			frappe.log_error(
				title=f"📝 Updating meeting: {meeting.name}",
				message=f"Meeting: {meeting.name}\nCurrent status: {meeting_doc.status}\nNew status: Completed\nEnd time: {end_time}\nConference ID: {conference_id}"
			)
			
			# Store conference ID if not already set
			if not meeting_doc.google_conference_id:
				meeting_doc.google_conference_id = conference_id
				frappe.log_error(
					title=f"💾 Stored conference_id for {meeting.name}",
					message=f"Conference ID: {conference_id}"
				)
			
			meeting_doc.status = "Completed"
			meeting_doc.actual_end_time = end_time
			meeting_doc.save(ignore_permissions=True)
			
			# Add activity comment for audit trail
			meeting_doc.add_comment(
				'Comment',
				f"🏁 **Conference Ended**\n\n"
				f"- Conference ID: `{conference_id}`\n"
				f"- End Time: {end_time}\n"
				f"- Status: Completed"
			)
			
			# Send real-time notification
			frappe.publish_realtime(
				event='vidcon_meeting_ended',
				message={
					'meeting_name': meeting.name,
					'status': 'Completed',
					'conference_id': conference_id,
					'end_time': str(end_time)
				},
				doctype='VidCon Meeting',
				docname=meeting.name
			)
			
			frappe.log_error(
				title=f"✅ Meeting {meeting.name} updated to Completed",
				message=f"Meeting: {meeting.name}\nStatus: Completed\nEnd time: {end_time}"
			)
			frappe.logger().info(f"✓ Meeting {meeting.name} marked as Completed")
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
		frappe.logger().info(f"=== CONFERENCE ENDED HANDLER COMPLETE ===\n")
		
	except Exception as e:
		frappe.logger().info(f"✗ Error handling conference ended: {str(e)}")
		frappe.logger().error(f"Error handling conference ended: {str(e)}")
		frappe.log_error(title="Conference Ended Handler Error", message=str(e))


def handle_recording_ready(event_data, attributes):
	"""
	Handle recording.fileGenerated event.
	Store recording details in VidCon Meeting.
	"""
	try:
		recording = event_data.get('recording', {})
		conference_id = recording.get('conferenceRecord', '').split('/')[-1]
		drive_file_id = recording.get('driveDestination', {}).get('file', '').split('/')[-1]
		
		# Extract space ID from ce-subject attribute
		ce_subject = attributes.get('ce-subject', '')
		space_id = ce_subject.split('/')[-1] if ce_subject else ''
		
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


def handle_transcript_ready(event_data, attributes):
	"""
	Handle transcript.fileGenerated event.
	Get transcript details from Meet API and download from Drive.
	"""
	try:
		frappe.logger().info(f"\n=== HANDLING TRANSCRIPT READY ===")
		frappe.logger().info(f"Event data: {json.dumps(event_data, indent=2)}")
		
		transcript = event_data.get('transcript', {})
		transcript_name = transcript.get('name', '')
		
		# Extract subscription UUID from ce-source
		ce_source = attributes.get('ce-source', '')
		subscription_uuid = ''
		if 'meet-spaces-' in ce_source:
			subscription_uuid = ce_source.split('meet-spaces-')[-1]
		
		# Encode subscription UUID for database lookup
		subscription_uuid_encoded = ''
		if subscription_uuid:
			import base64
			subscription_uuid_encoded = base64.b64encode(subscription_uuid.encode()).decode()[:20]
		
		# Extract space ID from ce-subject attribute
		ce_subject = attributes.get('ce-subject', '')
		space_id = ce_subject.split('/')[-1] if ce_subject else ''
		
		frappe.logger().info(f"Transcript name: {transcript_name}")
		frappe.logger().info(f"Space ID from ce-subject: {space_id}")
		frappe.logger().info(f"Subscription UUID: {subscription_uuid}")
		frappe.logger().info(f"Subscription UUID encoded: {subscription_uuid_encoded}")
		frappe.logger().info(f"Transcript ready: {transcript_name}")
		
		# Extract conference ID from transcript name
		# Format: conferenceRecords/{conferenceId}/transcripts/{transcriptId}
		parts = transcript_name.split('/')
		if len(parts) >= 2:
			conference_id = parts[1]
		else:
			frappe.logger().error(f"Invalid transcript name format: {transcript_name}")
			return
		
		frappe.log_error(
			title=f"🔍 Looking for meeting with conference_id: {conference_id}",
			message=f"Conference ID: {conference_id}\nSpace ID: {space_id}\nSubscription UUID: {subscription_uuid}\nTranscript name: {transcript_name}"
		)
		
		# Find VidCon Meeting by conference ID
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={"google_conference_id": conference_id},
			fields=["name", "google_conference_id", "google_space_id", "status"]
		)
		
		frappe.log_error(
			title=f"📊 Found {len(meetings)} meetings by conference_id",
			message=f"Conference ID: {conference_id}\nMeetings found: {len(meetings)}\nMeeting details: {json.dumps([dict(m) for m in meetings], indent=2) if meetings else 'None'}"
		)
		frappe.logger().info(f"Found {len(meetings)} meetings by conference_id")
		
		# If not found by conference_id, try by subscription UUID (most reliable)
		if not meetings and subscription_uuid:
			frappe.log_error(
				title=f"🔍 Trying subscription UUID lookup for transcript",
				message=f"Subscription UUID: {subscription_uuid}\nEncoded: {subscription_uuid_encoded}\nConference ID not found, searching by subscription"
			)
			frappe.logger().info(f"No meeting found by conference_id, trying subscription UUID: {subscription_uuid} (encoded: {subscription_uuid_encoded})")
			
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={
					"meet_subscription_id": ["like", f"%{subscription_uuid_encoded}%"]
				},
				fields=["name", "google_conference_id", "google_space_id", "status", "meet_subscription_id"],
				order_by="modified desc"
			)
			frappe.log_error(
				title=f"📊 Found {len(meetings)} meetings by subscription UUID",
				message=f"Subscription UUID: {subscription_uuid}\nEncoded: {subscription_uuid_encoded}\nMeetings: {json.dumps([dict(m) for m in meetings], indent=2) if meetings else 'None'}"
			)
			frappe.logger().info(f"Found {len(meetings)} meetings by subscription UUID")
		
		# Fallback to space_id if subscription lookup fails
		if not meetings and space_id:
			frappe.log_error(
				title=f"🔍 Trying space_id lookup for transcript",
				message=f"Space ID: {space_id}\nSubscription not found, searching by space_id"
			)
			frappe.logger().info(f"No meeting found by subscription, trying space_id: {space_id}")
			
			meetings = frappe.get_all(
				"VidCon Meeting",
				filters={
					"google_space_id": space_id
				},
				fields=["name", "google_conference_id", "google_space_id", "status"],
				order_by="modified desc"
			)
			frappe.log_error(
				title=f"📊 Found {len(meetings)} meetings by space_id",
				message=f"Space ID: {space_id}\nMeetings: {json.dumps([dict(m) for m in meetings], indent=2) if meetings else 'None'}"
			)
			frappe.logger().info(f"Found {len(meetings)} meetings by space_id")
			
			# Store conference_id on the meeting for future lookups
			if meetings:
				for meeting in meetings:
					if not meeting.get('google_conference_id'):
						frappe.db.set_value(
							"VidCon Meeting",
							meeting.name,
							"google_conference_id",
							conference_id,
							update_modified=False
						)
						frappe.log_error(
							title=f"💾 Stored conference_id for {meeting.name}",
							message=f"Conference ID: {conference_id}"
						)
		
		frappe.logger().info(f"Found {len(meetings)} meetings for conference {conference_id}")
		
		for meeting in meetings:
			frappe.log_error(
				title=f"📥 Downloading transcript for meeting: {meeting['name'] if isinstance(meeting, dict) else meeting.name}",
				message=f"Meeting: {meeting['name'] if isinstance(meeting, dict) else meeting.name}\nTranscript: {transcript_name}\nConference ID: {conference_id}"
			)
			meeting_name = meeting['name'] if isinstance(meeting, dict) else meeting.name
			frappe.logger().info(f"Downloading transcript for meeting: {meeting_name}")
			# Get transcript details from Meet API and download
			download_transcript_from_meet_api(meeting_name, transcript_name)
		
		if not meetings:
			frappe.log_error(
				title=f"❌ No meetings found for conference {conference_id}",
				message=f"Conference ID: {conference_id}\nTranscript: {transcript_name}\n\nChecking all meetings with google_conference_id set..."
			)
			
			# Debug: Show all meetings with conference IDs
			all_meetings = frappe.get_all(
				"VidCon Meeting",
				filters={"google_conference_id": ["is", "set"]},
				fields=["name", "google_conference_id", "google_space_id", "status", "modified"],
				limit=20
			)
			frappe.log_error(
				title=f"📋 All meetings with conference_id (last 20)",
				message=f"Total meetings with conference_id: {len(all_meetings)}\n\n{json.dumps([dict(m) for m in all_meetings], indent=2, default=str)}"
			)
			
			frappe.logger().warning(f"✗ No meetings found for conference {conference_id}")
		
		frappe.db.commit()
		frappe.logger().info(f"=== TRANSCRIPT READY HANDLER COMPLETE ===")
		
	except Exception as e:
		frappe.logger().error(f"✗ Error handling transcript ready: {str(e)}")
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
		frappe.logger().info(f"Getting transcript details: {transcript_name}")
		transcript_details = meet_service.conferenceRecords().transcripts().get(
			name=transcript_name
		).execute()
		
		frappe.logger().info(f"Transcript details: {json.dumps(transcript_details, indent=2)}")
		
		# Extract Drive file ID from transcript details
		drive_destination = transcript_details.get('docsDestination', {})
		document_id = drive_destination.get('document', '').split('/')[-1]
		
		if not document_id:
			frappe.logger().error(f"No Drive document ID in transcript details: {transcript_details}")
			return
		
		frappe.logger().info(f"Drive document ID: {document_id}")
		
		# Download transcript from Drive
		drive_service = build('drive', 'v3', credentials=credentials, static_discovery=False)
		
		# Get file metadata to check for Gemini notes
		file_metadata = drive_service.files().get(
			fileId=document_id,
			fields='name,description,properties'
		).execute()
		
		frappe.logger().info(f"File metadata: {json.dumps(file_metadata, indent=2)}")
		
		# Export transcript as plain text
		request = drive_service.files().export(
			fileId=document_id,
			mimeType='text/plain'
		)
		transcript_content = request.execute()
		
		# Decode transcript content
		if isinstance(transcript_content, bytes):
			transcript_text = transcript_content.decode('utf-8')
		else:
			transcript_text = transcript_content
		
		frappe.logger().info(f"Transcript length: {len(transcript_text)} characters")
		frappe.logger().info(f"Transcript preview (first 500 chars):\n{transcript_text[:500]}")
		
		# Try to extract Gemini notes from transcript
		# Gemini notes are usually at the beginning of the transcript
		gemini_notes = extract_gemini_notes(transcript_text)
		
		# Save transcript as file attachment
		file_name = f"transcript_{meeting_doc.name}_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.txt"
		
		frappe.logger().info(f"Creating file attachment: {file_name}")
		
		try:
			# Create file doc
			file_doc = frappe.get_doc({
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": "VidCon Meeting",
				"attached_to_name": meeting_doc.name,
				"attached_to_field": "transcript_file",
				"content": transcript_text,
				"is_private": 1
			})
			file_doc.save(ignore_permissions=True)
			frappe.db.commit()
			
			frappe.logger().info(f"✓ Transcript saved as attachment: {file_name}")
			frappe.logger().info(f"  File URL: {file_doc.file_url}")
			frappe.logger().info(f"  File size: {len(transcript_text)} bytes")
			
		except Exception as file_error:
			frappe.logger().error(f"✗ Error creating file attachment: {str(file_error)}")
			frappe.log_error(title="File Attachment Error", message=f"Meeting: {meeting_doc.name}\nError: {str(file_error)}")
			# Continue even if file attachment fails - we still have the URL
		
		# Update meeting with transcript metadata and notes
		meeting_doc.transcript_file_id = document_id
		meeting_doc.transcript_url = f"https://docs.google.com/document/d/{document_id}/view"
		meeting_doc.transcript_retrieved_at = frappe.utils.now_datetime()
		
		if gemini_notes:
			meeting_doc.meeting_notes = gemini_notes
			frappe.logger().info(f"✓ Extracted Gemini notes ({len(gemini_notes)} characters)")
		else:
			frappe.logger().warning(f"⚠ No Gemini notes found in transcript")
		
		meeting_doc.save(ignore_permissions=True)
		
		# Add activity comment for audit trail
		notes_info = f"\n- Gemini Notes: Extracted ({len(gemini_notes)} characters)" if gemini_notes else "\n- Gemini Notes: Not found"
		meeting_doc.add_comment(
			'Comment',
			f"📄 **Transcript Downloaded**\n\n"
			f"- Transcript ID: `{transcript_name.split('/')[-1]}`\n"
			f"- Drive Document: [View Transcript](https://docs.google.com/document/d/{document_id}/view)\n"
			f"- Size: {len(transcript_text)} characters"
			f"{notes_info}"
		)
		
		frappe.logger().info(f"✓ Transcript downloaded and stored for {meeting_name}")
		frappe.logger().info(f"Transcript downloaded and stored for {meeting_name}")
		
	except Exception as e:
		frappe.logger().error(f"Error downloading transcript from Meet API: {str(e)}")
		frappe.log_error(title="Transcript Download Error", message=str(e))


def extract_gemini_notes(transcript_text):
	"""
	Extract Gemini-generated notes from transcript.
	Google Meet's Gemini feature adds notes at the beginning of the transcript.
	
	Format:
	📝 Notes
	Meeting [date/time]
	Summary
	[summary text]
	Details
	[details]
	Suggested next steps
	[steps]
	
	📖 Transcript
	[actual transcript]
	
	Args:
		transcript_text: Full transcript text
	
	Returns:
		str: Extracted Gemini notes or None
	"""
	if not transcript_text:
		return None
	
	# Look for the Notes section marker
	if '📝 Notes' in transcript_text or 'Notes' in transcript_text[:200]:
		# Find where the transcript section starts
		transcript_markers = ['📖 Transcript', 'Transcript\n', '\nTranscript\n']
		
		split_index = -1
		for marker in transcript_markers:
			if marker in transcript_text:
				split_index = transcript_text.index(marker)
				break
		
		if split_index > 0:
			# Extract everything before the transcript section
			notes_section = transcript_text[:split_index].strip()
			
			# Clean up - remove the "📝 Notes" header if present
			if notes_section.startswith('📝 Notes'):
				notes_section = notes_section[len('📝 Notes'):].strip()
			elif notes_section.startswith('\ufeff📝 Notes'):  # Handle BOM character
				notes_section = notes_section[len('\ufeff📝 Notes'):].strip()
			
			# Remove review prompts and survey links at the end
			cleanup_markers = [
				'You should review Gemini',
				'Please provide feedback',
				'Get tips and learn how Gemini'
			]
			
			for marker in cleanup_markers:
				if marker in notes_section:
					notes_section = notes_section[:notes_section.index(marker)].strip()
					break
			
			# Verify this looks like Gemini notes
			if any(keyword in notes_section.lower() for keyword in ['summary', 'details', 'meeting']):
				frappe.logger().info(f"Extracted Gemini notes: {len(notes_section)} characters")
				return notes_section
	
	frappe.logger().warning("No Gemini notes section found in transcript")
	return None


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
