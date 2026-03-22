# Webhook Not Receiving Events - Diagnosis

**Issue:** No logs appearing in Error Log when meetings complete

## Quick Diagnosis Steps

### Step 1: Verify Pub/Sub Subscription Configuration

**Go to:** [Google Cloud Console](https://console.cloud.google.com/) → Pub/Sub → Subscriptions

**Find your subscription** (e.g., `meet-events-push`)

**Check:**
1. **Delivery Type** = Push ✅
2. **Endpoint URL** = `https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push` ✅
3. **State** = Active ✅

**Look at Metrics tab:**
- Published messages: Should be > 0 if events occurred
- Delivered messages: Should match published
- Delivery errors: Should be 0

### Step 2: Test Webhook Endpoint Directly

```bash
curl -X POST https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -d '{"message":{"data":"eyJ0ZXN0IjogInRlc3QifQ==","attributes":{},"messageId":"test"}}'
```

**Expected:** Should return `{"status": "ok"}` or similar

**If you get:**
- ❌ Connection refused → Server not accessible
- ❌ 404 Not Found → Endpoint path wrong
- ❌ SSL error → Certificate issue
- ✅ 200 OK → Endpoint is accessible

### Step 3: Check Pub/Sub Topic Configuration

**In Google Cloud Console:**
1. Go to Pub/Sub → Topics
2. Find your topic (e.g., `meet-events`)
3. Click on it
4. Check **Subscriptions** tab - should list your push subscription

### Step 4: Verify Workspace Events Subscription

**The subscription you created** (subscriptions/meet-spaces-...) is different from the Pub/Sub subscription.

**Workspace Events subscription:**
- Tells Google to send Meet events to Pub/Sub topic
- Created per meeting space
- Stored in `meet_subscription_id` field

**Pub/Sub subscription:**
- Tells Pub/Sub to push messages to your webhook
- Created once in Google Cloud Console
- Applies to all events on the topic

**Check if Workspace Events subscription exists:**
1. Open your VidCon Meeting
2. Check `meet_subscription_id` field
3. Should have value like: `subscriptions/meet-spaces-8b888669-cf0a-429d-b0f3-c25dd5c7ff35`

### Step 5: Check Google Cloud Logging

**Go to:** Google Cloud Console → Logging

**Filter:**
```
resource.type="pubsub_subscription"
resource.labels.subscription_id="meet-events-push"
```

**Look for:**
- Delivery attempts
- HTTP response codes from your webhook
- Error messages

## Common Issues

### Issue 1: Pub/Sub Subscription Not Configured

**Symptom:** No metrics, no delivery attempts

**Fix:**
1. Go to Google Cloud Console → Pub/Sub → Subscriptions
2. Click "Create Subscription"
3. Select your topic
4. Delivery type: Push
5. Endpoint URL: `https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`
6. Create

### Issue 2: Wrong Endpoint URL

**Check the URL carefully:**
- ✅ `https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`
- ❌ `http://` (must be HTTPS)
- ❌ Missing `/api/method/`
- ❌ Wrong domain

### Issue 3: Firewall Blocking Google

**Google's IP ranges need access:**
- Check nginx/firewall rules
- Ensure port 443 is open
- Allow Google's Pub/Sub IPs

### Issue 4: SSL Certificate Invalid

**Pub/Sub requires valid HTTPS:**
```bash
curl -I https://www.pema.co.za
```

Should show valid certificate, not self-signed.

### Issue 5: No Workspace Events Subscription

**Even if Pub/Sub is configured, you need per-meeting subscription:**

1. Open VidCon Meeting
2. Click "Create Meet Subscription" button
3. Should see: "Subscription already exists" or "Subscription created"
4. Check `meet_subscription_id` field is populated

## Testing the Full Flow

### Create Test Meeting

1. Create new VidCon Meeting
2. Click "Create Meet Subscription" button
3. Note the subscription ID
4. Join the Google Meet
5. End the meeting
6. Wait 2 minutes
7. Check Error Log for webhook calls

### Expected Logs (in order)

1. 🔔 **Pub/Sub Webhook Called** - When you join
2. 🚀 **Processing: conference.started**
3. ✅ **Webhook Processing Complete**
4. 🔔 **Pub/Sub Webhook Called** - When you leave
5. 🏁 **Processing: conference.ended**
6. ✅ **Webhook Processing Complete**

### If No Logs Appear

**Google is not calling your webhook. Check:**

1. **Pub/Sub subscription exists** in Google Cloud Console
2. **Endpoint URL is correct** in subscription
3. **Webhook is accessible** (test with curl)
4. **Workspace Events subscription exists** (meet_subscription_id field)
5. **Topic name matches** in VidCon Settings and Workspace subscription

## Verification Checklist

- [ ] Pub/Sub topic created in Google Cloud Console
- [ ] Pub/Sub push subscription created pointing to webhook
- [ ] Webhook endpoint accessible via HTTPS
- [ ] VidCon Settings → Enable Meet Events = Checked
- [ ] VidCon Settings → Pub/Sub Topic Name = `projects/YOUR_PROJECT/topics/meet-events`
- [ ] Meeting has `meet_subscription_id` populated
- [ ] Test curl to webhook returns 200 OK
- [ ] Google Cloud Logging shows delivery attempts

## Most Likely Issue

Based on "no logs at all", the most likely issue is:

**Pub/Sub push subscription is not configured or has wrong endpoint URL**

Go to Google Cloud Console → Pub/Sub → Subscriptions and verify the push subscription exists and points to the correct URL.

---

**Created:** March 22, 2026
