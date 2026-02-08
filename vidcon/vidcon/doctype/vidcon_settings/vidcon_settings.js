// Copyright (c) 2026, Pema and contributors
// For license information, please see license.txt

frappe.ui.form.on('VidCon Settings', {
	refresh: function(frm) {
		// Add button to authorize Google Calendar with extended scopes
		if (frm.doc.google_calendar && !frm.is_new()) {
			frm.add_custom_button(__('Authorize Google Calendar (VidCon)'), function() {
				frappe.call({
					method: 'vidcon.vidcon.doctype.vidcon_settings.google_auth.get_vidcon_auth_url',
					args: {
						google_calendar_name: frm.doc.google_calendar
					},
					callback: function(r) {
						if (r.message && r.message.url) {
							// Open authorization URL in new window
							window.open(r.message.url, '_blank');
							
							frappe.msgprint({
								title: __('Authorization Required'),
								message: __('Please complete the authorization in the new window. After authorizing, refresh this page and enable Meet Events.'),
								indicator: 'blue'
							});
						}
					}
				});
			}, __('Actions'));
		}
		
		// Add button to check subscription status
		if (frm.doc.meet_subscription_id) {
			frm.add_custom_button(__('Check Subscription Status'), function() {
				frappe.call({
					method: 'vidcon.vidcon.doctype.vidcon_meeting.subscription_manager.check_subscription_status',
					callback: function(r) {
						frm.reload_doc();
					}
				});
			}, __('Actions'));
		}
	}
});
