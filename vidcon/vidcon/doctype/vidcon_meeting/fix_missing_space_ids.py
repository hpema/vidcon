"""
Fix missing google_space_id for existing VidCon Meetings
Run this once to populate google_space_id from google_meet_link
"""

import frappe

def fix_missing_space_ids():
	"""Extract and set google_space_id from google_meet_link for all meetings"""
	
	# Get all meetings with Meet link but no space_id
	meetings = frappe.get_all(
		"VidCon Meeting",
		filters={
			"google_meet_link": ["!=", ""],
			"google_space_id": ["in", ["", None]]
		},
		fields=["name", "google_meet_link"]
	)
	
	if not meetings:
		print("No meetings need fixing")
		return
	
	print(f"Found {len(meetings)} meetings to fix")
	
	fixed = 0
	for meeting in meetings:
		try:
			# Extract space_id from Meet link
			# Format: https://meet.google.com/abc-defg-hij
			meet_link = meeting.get("google_meet_link")
			if meet_link:
				space_id = meet_link.split("/")[-1]
				
				# Update the meeting
				frappe.db.set_value(
					"VidCon Meeting",
					meeting.name,
					"google_space_id",
					space_id,
					update_modified=False
				)
				
				print(f"✓ Fixed {meeting.name}: space_id = {space_id}")
				fixed += 1
		except Exception as e:
			print(f"✗ Failed to fix {meeting.name}: {str(e)}")
	
	frappe.db.commit()
	print(f"\nFixed {fixed} out of {len(meetings)} meetings")

if __name__ == "__main__":
	fix_missing_space_ids()
