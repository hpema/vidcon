import frappe
from frappe.utils import now_datetime, add_to_date


def check_pending_transcripts():
	"""
	Scheduled task to check for meetings that have completed but don't have transcripts yet.
	Run every 15 minutes.
	"""
	try:
		# Find meetings that completed in the last 2 hours but don't have transcripts
		cutoff_time = add_to_date(now_datetime(), hours=-2)
		
		meetings = frappe.get_all(
			"VidCon Meeting",
			filters={
				"status": "Completed",
				"transcript": ["is", "not set"],
				"modified": [">=", cutoff_time]
			},
			fields=["name", "google_meet_link"]
		)
		
		for meeting in meetings:
			if meeting.google_meet_link:
				# Extract conference ID from Meet link
				conference_id = meeting.google_meet_link.split('/')[-1]
				
				# Enqueue transcript fetch
				frappe.enqueue(
					"vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.fetch_transcript_for_conference",
					queue="default",
					timeout=600,
					conference_id=conference_id,
					meeting_name=meeting.name
				)
				frappe.logger().info(f"Queued transcript fetch for {meeting.name}")
	
	except Exception as e:
		frappe.logger().error(f"Error in check_pending_transcripts: {str(e)}")
