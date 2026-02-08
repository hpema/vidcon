// Copyright (c) 2026, Pema and contributors
// For license information, please see license.txt

frappe.ui.form.on('VidCon Meeting', {
	refresh: function(frm) {
		// Add button to create Meet Events subscription
		if (frm.doc.google_meet_link && !frm.is_new()) {
			frm.add_custom_button(__('Create Meet Subscription'), function() {
				frappe.call({
					method: 'vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.create_meet_subscription',
					args: {
						meeting_name: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							frappe.msgprint({
								title: __('Subscription Created'),
								message: __('Subscription ID: {0}<br>State: {1}', [r.message.subscription_id, r.message.state]),
								indicator: 'green'
							});
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));
			
			// Show subscription status if exists
			if (frm.doc.meet_subscription_id) {
				frm.add_custom_button(__('Check Subscription Status'), function() {
					frappe.call({
						method: 'vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.check_subscription_status',
						args: {
							meeting_name: frm.doc.name
						},
						callback: function(r) {
							if (r.message) {
								frappe.msgprint({
									title: __('Subscription Status'),
									message: __('State: {0}<br>Subscription ID: {1}', [r.message.state, r.message.subscription_id]),
									indicator: r.message.state === 'ACTIVE' ? 'green' : 'orange'
								});
							}
						}
					});
				}, __('Actions'));
			}
		}
	}
});
