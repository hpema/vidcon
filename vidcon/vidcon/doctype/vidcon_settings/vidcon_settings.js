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
		
		// Add test webhook button if Meet Events is enabled
		if (frm.doc.enable_meet_events && !frm.is_new()) {
			frm.add_custom_button(__('Test Webhook'), function() {
				frappe.show_alert({
					message: __('Testing webhook endpoint...'),
					indicator: 'blue'
				});
				
				frappe.call({
					method: 'vidcon.vidcon.doctype.vidcon_settings.vidcon_settings.test_webhook_endpoint',
					callback: function(r) {
						if (r.message) {
							if (r.message.success) {
								frappe.msgprint({
									title: __('Webhook Test Successful'),
									message: __('Event was received and logged!<br><br>Event Log ID: {0}<br>Status Code: {1}<br><br>Check VidCon Event Log to see the test event.', 
										[r.message.event_log_id, r.message.status_code]),
									indicator: 'green'
								});
							} else {
								frappe.msgprint({
									title: __('Webhook Test Failed'),
									message: __('Error: {0}<br><br>Check Error Log for details.', [r.message.message]),
									indicator: 'red'
								});
							}
						}
					}
				});
			}, __('Actions'));
			
			// Show recent events status
			frm.add_custom_button(__('View Event Status'), function() {
				frappe.call({
					method: 'vidcon.vidcon.doctype.vidcon_settings.vidcon_settings.get_recent_events_status',
					callback: function(r) {
						if (r.message) {
							let status_html = `
								<div style="padding: 10px;">
									<h4>Event Status</h4>
									<p><strong>Total Events Received:</strong> ${r.message.total_events}</p>
									<p><strong>Last Event:</strong> ${r.message.last_event_time || 'No events yet'}</p>
									<hr>
									<h5>Recent Events:</h5>
									<ul>
							`;
							
							if (r.message.recent_events && r.message.recent_events.length > 0) {
								r.message.recent_events.forEach(function(event) {
									status_html += `<li>${event.received_at}: ${event.event_type} (${event.status})</li>`;
								});
							} else {
								status_html += '<li>No events received yet</li>';
							}
							
							status_html += `
									</ul>
									<p style="margin-top: 15px;">
										<a href="/app/vidcon-event-log">View All Events →</a>
									</p>
								</div>
							`;
							
							frappe.msgprint({
								title: __('Event Status'),
								message: status_html,
								indicator: r.message.total_events > 0 ? 'green' : 'orange'
							});
						}
					}
				});
			}, __('Actions'));
		}
	}
});
