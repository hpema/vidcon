"""
Patch Frappe's Dropbox Settings to handle missing pkg_resources gracefully.

This fixes compatibility with Python 3.12+ and modern packaging tools where
pkg_resources is not automatically available. The dropbox SDK (v11.36.2)
still depends on pkg_resources which causes import errors during migration.

This patch is applied automatically when VidCon is installed/updated.
"""
import frappe
import os


def execute():
	"""Patch Dropbox Settings to handle missing pkg_resources."""
	try:
		# Get the path to Frappe's Dropbox Settings
		frappe_path = frappe.get_app_path("frappe")
		dropbox_settings_path = os.path.join(
			frappe_path,
			"integrations",
			"doctype",
			"dropbox_settings",
			"dropbox_settings.py"
		)
		
		if not os.path.exists(dropbox_settings_path):
			frappe.log_error(
				title="Dropbox Settings Patch Skipped",
				message=f"File not found: {dropbox_settings_path}"
			)
			return
		
		# Read the current content
		with open(dropbox_settings_path, 'r') as f:
			content = f.read()
		
		# Check if already patched
		if "# VIDCON PATCH FOR PKG_RESOURCES" in content:
			frappe.log_error(
				title="Dropbox Settings Already Patched",
				message="VidCon patch already applied"
			)
			return
		
		# Find the import dropbox line
		original_import = "import dropbox"
		
		if original_import not in content:
			frappe.log_error(
				title="Dropbox Settings Patch Failed",
				message="Could not find 'import dropbox' statement to patch"
			)
			return
		
		# Create the patched import
		patched_import = """# VIDCON PATCH FOR PKG_RESOURCES COMPATIBILITY
# This patch handles missing pkg_resources in Python 3.12+
try:
	import dropbox
except ModuleNotFoundError as e:
	if "pkg_resources" in str(e):
		# Create a minimal pkg_resources stub to satisfy dropbox SDK
		import sys
		from types import ModuleType
		pkg_resources = ModuleType('pkg_resources')
		sys.modules['pkg_resources'] = pkg_resources
		import dropbox
	else:
		raise"""
		
		# Replace the import
		patched_content = content.replace(original_import, patched_import, 1)
		
		# Write the patched content back
		with open(dropbox_settings_path, 'w') as f:
			f.write(patched_content)
		
		frappe.log_error(
			title="Dropbox Settings Patched Successfully",
			message=f"Applied VidCon patch to {dropbox_settings_path}"
		)
		
		print("✓ Patched Frappe's Dropbox Settings for pkg_resources compatibility")
		
	except Exception as e:
		frappe.log_error(
			title="Dropbox Settings Patch Error",
			message=f"Error applying patch: {str(e)}"
		)
		print(f"✗ Failed to patch Dropbox Settings: {str(e)}")
