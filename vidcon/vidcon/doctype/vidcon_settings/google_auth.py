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
	
	# Build redirect URI
	redirect_uri = f"{get_request_site_address(full_address=True)}/api/method/frappe.integrations.doctype.google_calendar.google_calendar.google_callback"
	
	# Build authorization URL with extended scopes
	auth_url = (
		"https://accounts.google.com/o/oauth2/v2/auth?"
		f"access_type=offline&response_type=code&prompt=consent&client_id={google_settings.client_id}"
		f"&include_granted_scopes=true&scope={VIDCON_SCOPES}&redirect_uri={redirect_uri}"
	)
	
	return {
		"url": auth_url,
		"scopes": VIDCON_SCOPES
	}
