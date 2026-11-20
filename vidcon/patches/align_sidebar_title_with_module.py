"""Give vidcon's old desk sidebar its module's exact name before Frappe converts it.

Frappe's v16 sidebar conversion (frappe.patches.v16_0.convert_sidebars) builds a
new Sidebar for module "Vidcon" titled after the old one, "VidCon", and then
refuses it: a title may only be its own module's name, compared case-sensitively,
while the check for "another module's name" looks the title up case-insensitively
and finds "Vidcon". The update stopped there on sandbox.pema.co.za on 2026-11-20.

This runs in pre_model_sync, so before Frappe's post-sync patches. The only change
anyone sees is the desk label reading "Vidcon".
"""

import frappe


def execute():
	if not frappe.db.table_exists("Workspace Sidebar"):
		return
	scope = "and ifnull(for_user, '') = ''" if frappe.db.has_column("Workspace Sidebar", "for_user") else ""
	frappe.db.sql(
		f"""update `tabWorkspace Sidebar` set title = 'Vidcon'
		where name = 'VidCon' and (module = 'Vidcon' or ifnull(module, '') = '')
		and binary ifnull(title, '') != binary 'Vidcon' {scope}"""
	)
