"""
Google Workspace Events API Subscription Manager

Handles creation, deletion, and monitoring of Meet event subscriptions.
"""

import frappe
from frappe import _
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import requests


# VidCon scopes required for Workspace Events API
VIDCON_SCOPES = " ".join([
	"https://www.googleapis.com/auth/calendar",
	"https://www.googleapis.com/auth/meetings.space.readonly",
	"https://www.googleapis.com/auth/drive.readonly"
])


def get_vidcon_access_token(google_calendar_name):
	"""
	Get access token with VidCon scopes (calendar, meet, drive).
	
	This bypasses Frappe's get_access_token() which only requests calendar scope.
	"""
	google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
	google_settings = frappe.get_single("Google Settings")
	
	refresh_token = google_calendar.get_password("refresh_token", raise_exception=False)
	if not refresh_token:
		frappe.throw(_("Google Calendar is not authorized. Please authorize first."))
	
	# Request new access token with VidCon scopes
	token_data = {
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password("client_secret"),
		"refresh_token": refresh_token,
		"grant_type": "refresh_token",
		"scope": VIDCON_SCOPES
	}
	
	try:
		response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
		response.raise_for_status()
		tokens = response.json()
		return tokens.get("access_token")
	except Exception as e:
		frappe.log_error(title="VidCon Token Refresh Failed", message=str(e))
		frappe.throw(_("Failed to refresh access token: {0}").format(str(e)))


def get_cloud_identity_user_id(google_calendar_name, user_email):
	"""
	Get Cloud Identity user ID for an email address.
	Required for creating user-based Meet subscriptions.
	
	According to Google's documentation, for Workspace accounts, the user ID
	can be the email address itself when using cloudidentity.googleapis.com format.
	
	Args:
		google_calendar_name: Name of the Google Calendar document
		user_email: Email address of the user
	
	Returns:
		str: User identifier (email for Workspace accounts)
	"""
	# For Google Workspace accounts, the email address IS the valid user identifier
	# when using the //cloudidentity.googleapis.com/users/{user} format
	# Reference: https://developers.google.com/workspace/events/guides/events-meet
	return user_email


def create_meet_subscription(google_calendar_name, space_resource=None, user_email=None, pubsub_topic=None):
	"""
	Create a Google Workspace Events subscription for Meet events.
	
	Can create either space-based or user-based subscriptions:
	- Space-based: Monitor a specific meeting space (preferred)
	- User-based: Monitor all meetings for a user (fallback)
	
	Args:
		google_calendar_name: Name of the Google Calendar document
		space_resource: Space resource name (e.g., 'spaces/abc-defg-hij') for space-based subscription
		user_email: Email of the user to monitor for user-based subscription
		pubsub_topic: Full Pub/Sub topic name (projects/PROJECT_ID/topics/TOPIC)
	
	Returns:
		dict: Subscription response from Google API
	"""
	try:
		# Get Google Calendar and Google Settings
		google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
		google_settings = frappe.get_single("Google Settings")
		
		# Build credentials with VidCon scopes (calendar, meet, drive)
		credentials = Credentials(
			token=get_vidcon_access_token(google_calendar_name),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		# Build Workspace Events API service
		events_service = build('workspaceevents', 'v1', credentials=credentials, static_discovery=False)
		
		# Determine target resource
		if space_resource:
			# Space-based subscription for a specific meeting
			# Format: //meet.googleapis.com/spaces/{meetingCode}
			target_resource = f"//meet.googleapis.com/{space_resource}"
		elif user_email:
			# User-based subscription for all meetings where user is organizer
			# Format: //cloudidentity.googleapis.com/users/{email}
			target_resource = f"//cloudidentity.googleapis.com/users/{user_email}"
		else:
			frappe.throw(_("Either space_resource or user_email must be provided"))
		
		# Create subscription body
		subscription_body = {
			"targetResource": target_resource,
			"eventTypes": [
				"google.workspace.meet.conference.v2.started",
				"google.workspace.meet.conference.v2.ended",
				"google.workspace.meet.participant.v2.joined",
				"google.workspace.meet.participant.v2.left",
				"google.workspace.meet.transcript.v2.fileGenerated"
			],
			"notificationEndpoint": {
				"pubsubTopic": pubsub_topic
			},
			"payloadOptions": {
				"includeResource": False
			}
		}
		
		# Create subscription
		response = events_service.subscriptions().create(body=subscription_body).execute()
		
		frappe.logger().info(f"Meet subscription created: {response.get('name')}")
		
		return response
		
	except Exception as e:
		frappe.logger().error(f"Error creating Meet subscription: {str(e)}")
		raise


def delete_meet_subscription(google_calendar_name, subscription_id):
	"""
	Delete a Google Workspace Events subscription.
	
	Args:
		google_calendar_name: Name of the Google Calendar document
		subscription_id: Full subscription name from Google API
	"""
	try:
		# Get Google Calendar and Google Settings
		google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
		google_settings = frappe.get_single("Google Settings")
		
		# Build credentials with VidCon scopes (calendar, meet, drive)
		credentials = Credentials(
			token=get_vidcon_access_token(google_calendar_name),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		# Build Workspace Events API service
		events_service = build('workspaceevents', 'v1', credentials=credentials, static_discovery=False)
		
		# Delete subscription
		events_service.subscriptions().delete(name=subscription_id).execute()
		
		frappe.logger().info(f"Meet subscription deleted: {subscription_id}")
		
	except Exception as e:
		frappe.logger().error(f"Error deleting Meet subscription: {str(e)}")
		raise


def get_subscription_status(google_calendar_name, subscription_id):
	"""
	Get the status of a Google Workspace Events subscription.
	
	Args:
		google_calendar_name: Name of the Google Calendar document
		subscription_id: Full subscription name from Google API
	
	Returns:
		dict: Subscription details including state
	"""
	try:
		# Get Google Calendar and Google Settings
		google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
		google_settings = frappe.get_single("Google Settings")
		
		# Build credentials with VidCon scopes (calendar, meet, drive)
		credentials = Credentials(
			token=get_vidcon_access_token(google_calendar_name),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		# Build Workspace Events API service
		events_service = build('workspaceevents', 'v1', credentials=credentials, static_discovery=False)
		
		# Get subscription
		response = events_service.subscriptions().get(name=subscription_id).execute()
		
		return response
		
	except Exception as e:
		frappe.logger().error(f"Error getting subscription status: {str(e)}")
		raise


def list_subscriptions(google_calendar_name):
	"""
	List all Google Workspace Events subscriptions.
	
	Args:
		google_calendar_name: Name of the Google Calendar document
	
	Returns:
		list: List of subscriptions
	"""
	try:
		# Get Google Calendar and Google Settings
		google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
		google_settings = frappe.get_single("Google Settings")
		
		# Build credentials with VidCon scopes (calendar, meet, drive)
		credentials = Credentials(
			token=get_vidcon_access_token(google_calendar_name),
			refresh_token=google_calendar.get_password("refresh_token"),
			token_uri="https://oauth2.googleapis.com/token",
			client_id=google_settings.client_id,
			client_secret=google_settings.get_password("client_secret")
		)
		
		# Build Workspace Events API service
		events_service = build('workspaceevents', 'v1', credentials=credentials, static_discovery=False)
		
		# List subscriptions
		response = events_service.subscriptions().list().execute()
		
		return response.get('subscriptions', [])
		
	except Exception as e:
		frappe.logger().error(f"Error listing subscriptions: {str(e)}")
		raise


@frappe.whitelist()
def check_subscription_status():
	"""
	Whitelisted method to check subscription status from UI.
	Updates VidCon Settings with current subscription state.
	"""
	try:
		settings = frappe.get_single("VidCon Settings")
		
		if not settings.meet_subscription_id:
			frappe.msgprint(_("No active subscription found"), indicator="orange")
			return
		
		# Get subscription status
		response = get_subscription_status(
			settings.google_calendar,
			settings.meet_subscription_id
		)
		
		# Update settings
		settings.db_set("meet_subscription_state", response.get("state"), update_modified=False)
		
		state = response.get("state")
		if state == "ACTIVE":
			frappe.msgprint(_("Subscription is active"), indicator="green")
		elif state == "SUSPENDED":
			frappe.msgprint(_("Subscription is suspended"), indicator="orange")
		else:
			frappe.msgprint(_("Subscription state: {0}").format(state), indicator="blue")
		
		return response
		
	except Exception as e:
		frappe.log_error(title="Subscription Status Check Failed", message=str(e))
		frappe.msgprint(_("Failed to check subscription status: {0}").format(str(e)), indicator="red")
