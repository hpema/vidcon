"""
Authentication hooks for VidCon
Handles special authentication cases like Google Pub/Sub webhooks
"""

import frappe

def validate_vidcon_auth():
	"""
	Custom authentication for VidCon endpoints.
	Called by Frappe's auth_hooks system.
	"""
	# Check if this is the Pub/Sub webhook endpoint
	if frappe.request.path == '/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push':
		# Set user to Administrator to bypass the check at auth.py:627
		# That check fails if there's an Authorization header AND user is Guest
		# The webhook itself will handle JWT verification
		frappe.set_user("Administrator")
		frappe.local.login_manager.user = "Administrator"
