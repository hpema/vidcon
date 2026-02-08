"""
Custom Google OAuth authorization for VidCon with extended scopes.

Extends Frappe's Google Calendar authorization to include Meet and Drive scopes
required for Workspace Events API.
"""

import frappe
from frappe import _
from frappe.utils import get_request_site_address


# Required scopes for VidCon Meet Events integration
VIDCON_SCOPES = " ".join([
	"https://www.googleapis.com/auth/calendar",
	"https://www.googleapis.com/auth/meetings.space.readonly",
	"https://www.googleapis.com/auth/drive.readonly"
])


@frappe.whitelist()
def get_vidcon_auth_url(google_calendar_name):
	"""
	Generate OAuth authorization URL with VidCon-specific scopes.
	
	This extends the standard Google Calendar authorization to include
	Meet and Drive scopes required for Workspace Events API.
	"""
	# Get Google Settings
	google_settings = frappe.get_single("Google Settings")
	
	if not google_settings.enable:
		frappe.throw(_("Enable Google API in Google Settings."))
	
	if not google_settings.client_id or not google_settings.client_secret:
		frappe.throw(_("Enter Client Id and Client Secret in Google Settings."))
	
	# Store calendar name in cache for callback
	frappe.cache.hset("google_calendar", "google_calendar", google_calendar_name)
	
	# Build redirect URI - use VidCon's own callback
	redirect_uri = f"{get_request_site_address(full_address=True)}/api/method/vidcon.vidcon.doctype.vidcon_settings.google_auth.vidcon_callback"
	
	# Build authorization URL with extended scopes
	auth_url = (
		"https://accounts.google.com/o/oauth2/v2/auth?"
		f"access_type=offline&response_type=code&prompt=consent&client_id={google_settings.client_id}"
		f"&include_granted_scopes=true&scope={VIDCON_SCOPES}&redirect_uri={redirect_uri}"
	)
	
	return {
		"url": auth_url,
		"scopes": VIDCON_SCOPES,
		"redirect_uri": redirect_uri
	}


@frappe.whitelist(allow_guest=True)
def vidcon_callback(code=None):
	"""
	OAuth callback handler for VidCon Google authorization.
	Receives authorization code and exchanges it for tokens.
	"""
	import requests
	
	if not code:
		frappe.respond_as_web_page(
			_("Error"),
			_("No authorization code received from Google."),
			indicator_color="red"
		)
		return
	
	try:
		# Get calendar name from cache
		google_calendar_name = frappe.cache.hget("google_calendar", "google_calendar")
		
		if not google_calendar_name:
			frappe.respond_as_web_page(
				_("Error"),
				_("Session expired. Please try authorizing again."),
				indicator_color="red"
			)
			return
		
		# Get Google Settings
		google_settings = frappe.get_single("Google Settings")
		
		# Build redirect URI (must match the one used in authorization)
		redirect_uri = f"{get_request_site_address(full_address=True)}/api/method/vidcon.vidcon.doctype.vidcon_settings.google_auth.vidcon_callback"
		
		# Exchange authorization code for tokens
		token_data = {
			"code": code,
			"client_id": google_settings.client_id,
			"client_secret": google_settings.get_password("client_secret"),
			"redirect_uri": redirect_uri,
			"grant_type": "authorization_code"
		}
		
		response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
		response.raise_for_status()
		tokens = response.json()
		
		# Store tokens in Google Calendar document
		google_calendar = frappe.get_doc("Google Calendar", google_calendar_name)
		google_calendar.set_value("authorization_code", code)
		google_calendar.set_value("refresh_token", tokens.get("refresh_token"))
		frappe.db.commit()
		
		# Clear cache
		frappe.cache.hdel("google_calendar", "google_calendar")
		
		# Success response
		frappe.respond_as_web_page(
			_("Authorization Successful"),
			_("Google Calendar has been authorized with VidCon scopes (Calendar, Meet, Drive). You can now close this window and enable Meet Events in VidCon Settings."),
			indicator_color="green"
		)
		
	except Exception as e:
		frappe.log_error(title="VidCon OAuth Callback Error", message=str(e))
		frappe.respond_as_web_page(
			_("Authorization Failed"),
			_("Failed to complete authorization: {0}").format(str(e)),
			indicator_color="red"
		)
