# VidCon Production Deployment Checklist

## Pre-Deployment: Google Cloud Setup

### 1. Enable Required APIs
Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Library

- [x] Google Calendar API (already enabled)
- [ ] Google Meet API
- [ ] Google Workspace Events API  
- [ ] Google Drive API
- [ ] Cloud Pub/Sub API

### 2. Update OAuth Scopes
Go to APIs & Services → OAuth consent screen → Edit App → Scopes

Add these scopes:
```
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/meetings.space.readonly
https://www.googleapis.com/auth/drive.readonly
```

### 3. Create Pub/Sub Topic
Go to Pub/Sub → Topics → Create Topic

- **Topic ID**: `meet-events`
- **Full name**: `projects/YOUR_PROJECT_ID/topics/meet-events`
- Copy the full topic name for VidCon Settings

### 4. Grant Pub/Sub Publisher Permission
In the topic details → Permissions tab:

- Click **Add Principal**
- Principal: `meet-api-event-push@system.gserviceaccount.com`
- Role: **Pub/Sub Publisher**
- Save

### 5. Create Push Subscription
In the topic details → Subscriptions → Create Subscription

- **Subscription ID**: `meet-events-push`
- **Delivery type**: Push
- **Endpoint URL**: `https://YOUR_DOMAIN/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`
- Click Create

**Important**: Replace `YOUR_DOMAIN` with your actual production domain (e.g., `www.pema.co.za`)

### 6. Update OAuth Redirect URIs
Go to APIs & Services → Credentials → Your OAuth 2.0 Client ID

Add authorized redirect URI:
```
https://YOUR_DOMAIN
```

(The callback parameter will be appended automatically by Frappe)

## Deployment Steps

### 1. Pull Latest Code on Production
```bash
cd /path/to/frappe-bench
cd apps/vidcon
git pull origin main
```

### 2. Run Migrations
```bash
bench --site YOUR_SITE migrate
```

### 3. Clear Cache
```bash
bench --site YOUR_SITE clear-cache
bench --site YOUR_SITE clear-website-cache
```

### 4. Restart Services
```bash
bench restart
```

## Configuration Steps

### 1. Authorize Google Calendar
1. In ERPNext, go to **Google Calendar** list
2. Open your calendar document (e.g., "Business Meetings")
3. Click **"Authorize API Access"** button
4. Complete OAuth flow with Google
5. Verify successful authorization

**Verify in console:**
```bash
bench --site YOUR_SITE console <<'EOF'
import frappe
has_token = frappe.db.exists("__Auth", {
    "doctype": "Google Calendar",
    "name": "YOUR_CALENDAR_NAME",
    "fieldname": "access_token"
})
print(f"Access token exists: {bool(has_token)}")
EOF
```

Should output: `Access token exists: True`

### 2. Configure VidCon Settings
1. Search for **VidCon Settings** (Ctrl+K)
2. Fill in required fields:
   - **Google Calendar**: Select your authorized calendar
   - **Meeting Organizer Email**: Your email (e.g., `you@yourdomain.com`)
   - **Pub/Sub Topic Name**: `projects/YOUR_PROJECT_ID/topics/meet-events`
3. **Don't check "Enable Meet Events" yet**
4. Click **Save**

### 3. Enable Meet Events
1. Check **"Enable Meet Events"** checkbox
2. Click **Save**
3. Watch for success message: "Meet Events subscription created successfully!"

**Verify subscription:**
```bash
bench --site YOUR_SITE console <<'EOF'
import frappe
settings = frappe.get_single("VidCon Settings")
print(f"Subscription ID: {settings.meet_subscription_id}")
print(f"Subscription State: {settings.meet_subscription_state}")
print(f"Target User: {settings.subscription_target_user}")
EOF
```

Should show:
- Subscription ID: `subscriptions/...`
- Subscription State: `ACTIVE`
- Target User: Your email

## Testing

### 1. Create Test Meeting
1. Go to **VidCon Meeting** → New
2. Fill in:
   - Title: "Test Meeting"
   - Date: Today
   - Start/End Time: Next hour
3. Save
4. Verify Google Meet link is generated
5. Check that `google_space_id` is populated (hidden field)

### 2. Test Meeting Flow (Manual for now)
1. Join the meeting
2. End the meeting
3. Check VidCon Meeting record:
   - Status should update (when Pub/Sub handler is complete)
   - Participants should be tracked (when handler is complete)

## Troubleshooting

### Google Calendar Authorization Fails
- Check OAuth redirect URI in Google Cloud Console
- Verify `host_name` in site_config.json (should be `https://YOUR_DOMAIN` or `https://YOUR_DOMAIN:443`)
- Check Error Log in ERPNext for details

### Subscription Creation Fails
**Error**: "Pub/Sub Topic Name is required"
- Ensure topic name is in format: `projects/PROJECT_ID/topics/meet-events`

**Error**: "Google Calendar is not authorized"
- Complete Google Calendar authorization first
- Verify access_token exists in __Auth table

**Error**: API quota exceeded
- Check Google Cloud Console → APIs & Services → Quotas
- Request quota increase if needed

### Subscription Shows SUSPENDED
- Check Google Cloud Console → Pub/Sub → Subscriptions
- Verify endpoint URL is accessible from internet
- Check push subscription delivery metrics

### Webhook Not Receiving Events
- Verify site is accessible via HTTPS (required by Google)
- Check push subscription endpoint URL is correct
- Test endpoint manually:
  ```bash
  curl -X POST https://YOUR_DOMAIN/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
    -H "Content-Type: application/json" \
    -d '{"message":{"data":""}}'
  ```

## Post-Deployment

### Monitor Logs
```bash
# Watch for webhook activity
tail -f /path/to/frappe-bench/logs/web.error.log | grep -i "meet_events\|pubsub"

# Check Error Log in ERPNext
# Go to: Error Log list, filter by method containing "meet_events"
```

### Verify Pub/Sub Metrics
Go to Google Cloud Console → Pub/Sub → Subscriptions → `meet-events-push`

Check:
- Message delivery rate
- Acknowledgment rate
- Delivery errors

## Next Steps

1. **Complete Pub/Sub Event Handler** - Implement event processing logic in `google_meet_events.py`
2. **Test End-to-End Flow** - Create meeting, join, end, verify transcript retrieval
3. **Add CRM Integration** - Link meetings to Deals/Leads
4. **Build Analytics** - Meeting metrics and reporting

## Rollback Plan

If issues occur:

```bash
# Disable Meet Events in VidCon Settings (unchecks the box)
# This will automatically delete the subscription

# Or manually via console:
bench --site YOUR_SITE console <<'EOF'
from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import delete_meet_subscription
settings = frappe.get_single("VidCon Settings")
if settings.meet_subscription_id:
    delete_meet_subscription(settings.google_calendar, settings.meet_subscription_id)
    settings.db_set("meet_subscription_id", None)
    settings.db_set("meet_subscription_state", None)
    print("Subscription deleted")
EOF
```

## Support

- GitHub Issues: https://github.com/hpema/vidcon/issues
- Documentation: See ARCHITECTURE.md, PUBSUB_SETUP.md
- Google Workspace Events API: https://developers.google.com/workspace/events
