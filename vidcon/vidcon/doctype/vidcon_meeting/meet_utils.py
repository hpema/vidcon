"""
Utility functions for Google Meet integration
"""

import re
import frappe
from frappe import _


def extract_space_id_from_meet_link(meet_link):
	"""
	Extract the space ID from a Google Meet link.
	
	Args:
		meet_link: Google Meet URL (e.g., https://meet.google.com/abc-defg-hij)
	
	Returns:
		str: Space ID (e.g., 'abc-defg-hij') or None if not found
	
	Examples:
		>>> extract_space_id_from_meet_link('https://meet.google.com/abc-defg-hij')
		'abc-defg-hij'
		>>> extract_space_id_from_meet_link('meet.google.com/xyz-abcd-efg')
		'xyz-abcd-efg'
	"""
	if not meet_link:
		return None
	
	# Pattern: meet.google.com/{space_id}
	# Space ID format: xxx-xxxx-xxx (3 groups separated by hyphens)
	pattern = r'meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})'
	
	match = re.search(pattern, meet_link)
	if match:
		return match.group(1)
	
	return None


def create_space_subscription(meeting_doc):
	"""
	Create a Google Workspace Events subscription for a meeting's space.
	
	Args:
		meeting_doc: VidCon Meeting document
	
	Returns:
		dict: Subscription response or None if failed
	"""
	# Check if Meet Events is enabled
	settings = frappe.get_single("VidCon Settings")
	if not settings.enable_meet_events:
		return None
	
	# Extract meeting code from Meet link
	meeting_code = extract_space_id_from_meet_link(meeting_doc.google_meet_link)
	if not meeting_code:
		frappe.log_error(
			title="Invalid Meet Link",
			message=f"Could not extract meeting code from: {meeting_doc.google_meet_link}"
		)
		return None
	
	try:
		from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import create_meet_subscription
		
		# Create subscription using spaces/{meetingCode} format
		# According to Google's docs, meetingCode can be used as an alias for space ID
		space_resource = f"spaces/{meeting_code}"
		
		response = create_meet_subscription(
			google_calendar_name=settings.google_calendar,
			space_resource=space_resource,
			pubsub_topic=settings.pubsub_topic_name
		)
		
		frappe.logger().info(f"Created subscription for meeting {meeting_doc.name}: {response.get('name')}")
		
		return response
		
	except Exception as e:
		frappe.log_error(
			title="Meet Subscription Creation Failed",
			message=f"Meeting: {meeting_doc.name}\nSpace ID: {space_id}\nError: {str(e)}"
		)
		return None


def delete_space_subscription(subscription_id):
	"""
	Delete a Google Workspace Events subscription.
	
	Args:
		subscription_id: Full subscription name from Google API
	"""
	if not subscription_id:
		return
	
	settings = frappe.get_single("VidCon Settings")
	if not settings.enable_meet_events:
		return
	
	try:
		from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import delete_meet_subscription
		
		delete_meet_subscription(
			google_calendar_name=settings.google_calendar,
			subscription_id=subscription_id
		)
		
		frappe.logger().info(f"Deleted subscription: {subscription_id}")
		
	except Exception as e:
		frappe.log_error(
			title="Meet Subscription Deletion Failed",
			message=f"Subscription ID: {subscription_id}\nError: {str(e)}"
		)
