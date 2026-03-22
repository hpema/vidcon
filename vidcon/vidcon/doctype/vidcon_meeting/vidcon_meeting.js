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
		
		// Add button to sync from Google Meet API (works for any status)
		if (frm.doc.google_space_id && !frm.is_new()) {
			frm.add_custom_button(__('Sync from Google Meet'), function() {
				frappe.confirm(
					__('Fetch latest meeting data from Google Meet API?<br><br>This will update:<br>• Meeting status<br>• Start/end times<br>• Conference ID<br>• Transcript (if available)'),
					function() {
						frappe.call({
							method: 'vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.sync_from_google_meet',
							args: {
								meeting_name: frm.doc.name
							},
							freeze: true,
							freeze_message: __('Syncing from Google Meet...'),
							callback: function(r) {
								if (r.message && r.message.success) {
									frappe.show_alert({
										message: __(r.message.message),
										indicator: 'green'
									}, 5);
									frm.reload_doc();
								}
							}
						});
					}
				);
			}, __('Actions'));
		}
		
		// Add button to manually fetch transcript for completed meetings
		if (frm.doc.google_conference_id && 
		    ['Completed', 'In Progress'].includes(frm.doc.status) && 
		    !frm.is_new()) {
			frm.add_custom_button(__('Fetch Transcript'), function() {
				frappe.confirm(
					__('Fetch transcript from Google Meet API?'),
					function() {
						frappe.call({
							method: 'vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.fetch_transcript_manually',
							args: {
								meeting_name: frm.doc.name
							},
							freeze: true,
							freeze_message: __('Fetching transcript...'),
							callback: function(r) {
								if (r.message && r.message.success) {
									frappe.show_alert({
										message: __('Transcript fetched successfully!'),
										indicator: 'green'
									}, 5);
									frm.reload_doc();
								}
							}
						});
					}
				);
			}, __('Actions'));
		}
	}
});
