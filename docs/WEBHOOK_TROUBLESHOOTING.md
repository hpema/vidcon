# Webhook Troubleshooting Guide

**Issue:** Meeting completed but VidCon not receiving Pub/Sub events (status not updating, no transcript)

## Quick Diagnosis Checklist

### ✅ Step 1: Check Google Cloud Pub/Sub Subscription

**Location:** [Google Cloud Console](https://console.cloud.google.com/) → Pub/Sub → Subscriptions

1. Find your subscription (e.g., `meet-events-push`)
2. Click on it
3. Check **Metrics** tab:
   - Are messages being published? (should see activity)
   - Are messages being delivered? (should match published)
   - Any delivery errors? (red flags)

**What to look for:**
- ✅ **Published messages > 0** = Google is sending events
- ❌ **Delivery errors > 0** = Your webhook is unreachable or returning errors
- ❌ **Undelivered messages > 0** = Messages stuck in queue

### ✅ Step 2: Test Webhook Endpoint Directly

**Test if your webhook is accessible:**

```bash
# Replace YOUR_DOMAIN with your actual domain
curl -X POST https://YOUR_DOMAIN/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -d '{"message":{"data":"eyJ0ZXN0IjogInRlc3QifQ==","attributes":{},"messageId":"test"}}'
```

**Expected response:**
```json
{"status": "ok"}
```

**If you get:**
- ❌ **Connection refused** = Server not running or firewall blocking
- ❌ **404 Not Found** = Endpoint path wrong or app not installed
- ❌ **SSL error** = HTTPS certificate issue
- ✅ **200 OK with {"status": "ok"}** = Webhook working!

### ✅ Step 3: Check VidCon Error Logs

**In Frappe:**

1. Go to **Error Log** list
2. Filter by:
   - **Method** contains: `google_meet_events`
   - **Creation** > Last 24 hours
3. Look for errors

**Or via console:**
```python
frappe.get_all("Error Log", 
    filters={
        "method": ["like", "%google_meet_events%"],
        "creation": [">", "2026-03-22"]
    },
    fields=["creation", "error", "method"],
    order_by="creation desc",
    limit=20
)
```

### ✅ Step 4: Verify Meet Subscription Was Created

**Check if subscription exists for your meeting:**

1. Open your VidCon Meeting
2. Check if `meet_subscription_id` field has a value
3. If empty, subscription was never created

**Why subscription might be missing:**
- `enable_meet_events` disabled in VidCon Settings
- Error during subscription creation (check Error Log)
- Meeting created before feature was enabled

### ✅ Step 5: Check VidCon Settings

**Go to VidCon Settings and verify:**

- ✅ **Google Calendar** = Selected
- ✅ **Enable Meet Events** = Checked
- ✅ **Pub/Sub Topic Name** = `projects/YOUR_PROJECT_ID/topics/meet-events`

**If Pub/Sub Topic Name is empty:**
- This is critical! Subscriptions won't be created
- Format: `projects/YOUR_PROJECT_ID/topics/meet-events`

### ✅ Step 6: Verify OAuth Scopes

**Required scopes:**
```
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/meetings.space.readonly
https://www.googleapis.com/auth/drive.readonly
```

**To verify:**
1. Go to Google Calendar list
2. Open your calendar
3. Click **Authorize API Access**
4. Check granted permissions

**If scopes missing:**
1. Add them in Google Cloud Console → OAuth consent screen
2. Re-authorize in Frappe

## Common Issues & Solutions

### Issue 1: "No conference found" when syncing

**Cause:** Meeting was never started (no one joined)

**Solution:** 
- Meeting must be actually started for conference to exist
- Use "Sync from Google Meet" button after someone joins

### Issue 2: Webhook returns 401 Unauthorized

**Cause:** JWT verification failing

**Solution:**
- Check if `allow_guest=True` on webhook endpoint
- Verify Google's public keys are accessible
- Check Error Log for JWT verification errors

### Issue 3: Messages delivered but nothing happens

**Cause:** Event handler can't find meeting

**Solution:**
- Check if `google_space_id` is set on meeting
- Verify event handlers are using space_id matching (recent fix)
- Use "Sync from Google Meet" to recover

### Issue 4: Subscription not created for new meetings

**Cause:** `enable_meet_events` disabled or Pub/Sub topic not configured

**Solution:**
1. Enable in VidCon Settings
2. Set Pub/Sub topic name
3. Manually create subscription using "Create Meet Subscription" button

### Issue 5: SSL/HTTPS errors in Pub/Sub delivery

**Cause:** Invalid SSL certificate or HTTP (not HTTPS)

**Solution:**
- Pub/Sub requires valid HTTPS
- Use Let's Encrypt or valid SSL certificate
- Test with: `curl -I https://your-domain.com`

## Testing Tools

### 1. Google Cloud Console - Pub/Sub Subscription Metrics

**Best for:** Seeing if messages are being sent and delivered

**Location:**
1. [Google Cloud Console](https://console.cloud.google.com/)
2. Pub/Sub → Subscriptions
3. Click your subscription
4. Metrics tab

**What you'll see:**
- Published messages (from Google)
- Delivered messages (to your webhook)
- Delivery errors (with error messages)
- Latency graphs

### 2. Pub/Sub Message Pull (Manual)

**Best for:** Seeing actual message content

**Steps:**
1. In subscription details, click **Messages** tab
2. Click **Pull** button
3. View message content
4. Can manually acknowledge or reject

**Note:** Only works if delivery type is "Pull" not "Push"

### 3. Cloud Logging

**Best for:** Detailed delivery logs

**Location:**
1. Google Cloud Console → Logging
2. Filter:
   ```
   resource.type="pubsub_subscription"
   resource.labels.subscription_id="meet-events-push"
   ```

**Shows:**
- Delivery attempts
- HTTP response codes
- Error messages from your endpoint

### 4. Local Webhook Testing

**Best for:** Testing endpoint without Google

**Using curl:**
```bash
curl -X POST http://localhost:8000/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "data": "eyJjb25mZXJlbmNlUmVjb3JkIjp7Im5hbWUiOiJjb25mZXJlbmNlUmVjb3Jkcy90ZXN0MTIzIiwic3BhY2UiOiJzcGFjZXMvYWJjLWRlZmctaGlqIiwic3RhcnRUaW1lIjoiMjAyNi0wMy0yMlQxMDowMDowMFoiLCJlbmRUaW1lIjoiMjAyNi0wMy0yMlQxMTowMDowMFoifX0=",
      "attributes": {
        "ce-type": "google.workspace.meet.conference.v2.ended"
      },
      "messageId": "test-123"
    },
    "subscription": "projects/test/subscriptions/test"
  }'
```

**Decode the data field:**
```python
import base64
import json

data = "eyJjb25mZXJlbmNlUmVjb3JkIjp7Im5hbWUiOiJjb25mZXJlbmNlUmVjb3Jkcy90ZXN0MTIzIiwic3BhY2UiOiJzcGFjZXMvYWJjLWRlZmctaGlqIiwic3RhcnRUaW1lIjoiMjAyNi0wMy0yMlQxMDowMDowMFoiLCJlbmRUaW1lIjoiMjAyNi0wMy0yMlQxMTowMDowMFoifX0="
decoded = base64.b64decode(data).decode('utf-8')
print(json.dumps(json.loads(decoded), indent=2))
```

## Recovery Steps

### If Webhook Was Never Working:

1. **Fix the root cause** (see diagnosis above)
2. **For existing meetings:** Use "Sync from Google Meet" button
3. **For future meetings:** Verify subscription creation works

### If Webhook Stopped Working:

1. **Check Pub/Sub subscription status** in Google Cloud Console
2. **Verify SSL certificate** hasn't expired
3. **Check Error Logs** for recent failures
4. **Test endpoint** with curl
5. **Recreate subscription** if needed

### Manual Recovery for Old Meetings:

```python
# In Frappe console
meetings = frappe.get_all(
    "VidCon Meeting",
    filters={
        "status": "Scheduled",
        "meeting_date": ["<", frappe.utils.today()],
        "google_space_id": ["!=", ""]
    },
    fields=["name"]
)

for meeting in meetings:
    print(f"Syncing {meeting.name}...")
    frappe.call(
        "vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.sync_from_google_meet",
        meeting_name=meeting.name
    )
```

## Verification Checklist

After fixing issues, verify:

- [ ] Create new test meeting
- [ ] Verify `meet_subscription_id` is set
- [ ] Start meeting (join with participant)
- [ ] Check Error Log for "HANDLING CONFERENCE STARTED" message
- [ ] Verify status changes to "In Progress"
- [ ] End meeting
- [ ] Check Error Log for "HANDLING CONFERENCE ENDED" message
- [ ] Verify status changes to "Completed"
- [ ] Wait 15 minutes
- [ ] Check Error Log for "HANDLING TRANSCRIPT READY" message
- [ ] Verify transcript is downloaded

## Quick Reference

**Webhook Endpoint:**
```
https://YOUR_DOMAIN/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push
```

**Required Headers:**
- Content-Type: application/json
- Authorization: Bearer [JWT from Google]

**Response:**
- Success: `{"status": "ok"}` (200)
- Error: `{"status": "error", "message": "..."}` (200)

**Note:** Always return 200 to prevent Pub/Sub retries

---

**Created:** March 22, 2026  
**Related:** MEETING_STATUS_FIX.md, SYNC_FROM_GOOGLE.md, PUBSUB_SETUP.md
