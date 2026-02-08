import frappe

def execute():
	"""
	Fix event_type field length in VidCon Event Log.
	The field needs to be 200 characters to accommodate long Google event type names.
	"""
	frappe.reload_doctype("VidCon Event Log", force=True)
	frappe.db.commit()
