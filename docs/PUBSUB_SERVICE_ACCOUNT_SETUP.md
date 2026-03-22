# Pub/Sub Service Account Configuration - Complete Checklist

## What You Need to Configure

When you enable service account authentication on your Pub/Sub push subscription, Google will send JWT tokens in the `Authorization` header. Here's what needs to be configured:

## 1. Pub/Sub Push Subscription Configuration

### In Google Cloud Console

**Navigate to:** Pub/Sub → Subscriptions → [Your Subscription]

**Required Settings:**

1. **Delivery Type:** Push ✅
2. **Endpoint URL:** `https://dev.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`
3. **Authentication:**
   - **Enable authentication:** ✅ Checked
   - **Service account:** Select a service account
   - **Audience:** Should auto-populate with your endpoint URL

### Service Account Selection

You have two options:

**Option A: Use Compute Engine Default Service Account**
- Automatically available
- Format: `PROJECT_NUMBER-compute@developer.gserviceaccount.com`
- Easiest option

**Option B: Create Custom Service Account**
1. Go to IAM & Admin → Service Accounts
2. Create new service account
3. Name: `pubsub-push-invoker`
4. Grant role: `Pub/Sub Publisher`
5. Use this service account in subscription

## 2. Verify JWT Token Configuration

### Expected Audience

The JWT token's `aud` (audience) claim must match your webhook URL:

```
https://dev.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push
```

**Important:** 
- Must be HTTPS (not HTTP)
- Must be the full URL including domain
- Must match exactly (no trailing slash)

### JWT Token Structure

When properly configured, Google sends:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEyMzQ1In0...
```

The decoded JWT contains:
```json
{
  "iss": "https://accounts.google.com",
  "sub": "SERVICE_ACCOUNT_ID",
  "aud": "https://dev.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push",
  "email": "SERVICE_ACCOUNT_EMAIL",
  "exp": 1234567890,
  "iat": 1234567890
}
```

## 3. Test the Configuration

### Step 1: Publish Test Message

1. Go to Google Cloud Console → Pub/Sub → Topics
2. Click your topic → **PUBLISH MESSAGE**
3. Add attributes:
   - `ce-type`: `google.workspace.meet.conference.v2.ended`
   - `ce-source`: `//meet.googleapis.com/spaces/test-space-id`
   - `ce-subject`: `conferenceRecords/test-123`
   - `ce-id`: `test-event-123`
4. Message body:
```json
{
  "conferenceRecord": {
    "name": "conferenceRecords/test-123",
    "space": "spaces/test-space-id",
    "startTime": "2026-03-22T18:00:00Z",
    "endTime": "2026-03-22T18:30:00Z"
  }
}
```
5. Click **PUBLISH**

### Step 2: Check Frappe Error Log

In Frappe, go to **Error Log** and look for:

**With JWT Token (Correct):**
```
🔑 JWT Token Received
Token length: 850 characters
First 50 chars: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEy...
```

**Without JWT Token (Incorrect):**
```
⚠️ No JWT Token - Proceeding Without Auth
Authorization header: EMPTY
```

### Step 3: Verify JWT Verification

If JWT token is present, you should see:

**Success:**
```
✅ JWT Verified Successfully
Verified token for: SERVICE_ACCOUNT_EMAIL
Issuer: https://accounts.google.com
```

**Failure:**
```
❌ JWT Verification Failed
Invalid or expired JWT token from Pub/Sub
```

## 4. Common Issues and Fixes

### Issue 1: "Authorization header: EMPTY"

**Cause:** Service account authentication not enabled on subscription

**Fix:**
1. Edit Pub/Sub subscription
2. Enable authentication
3. Select service account
4. Save

### Issue 2: "JWT Verification Failed"

**Possible Causes:**

**A. Audience Mismatch**
- JWT `aud` claim doesn't match webhook URL
- Check if URL has trailing slash or wrong protocol

**Fix:**
```python
# Check expected audience in logs
# Should match exactly: https://dev.pema.co.za/api/method/...
```

**B. Expired Token**
- JWT has expired (unlikely for fresh requests)
- Check system time is correct

**C. Invalid Signature**
- Google's public keys changed (rare)
- Webhook can't fetch Google's public keys

**Fix:** Check internet connectivity from server

### Issue 3: "Could not fetch Google's public keys"

**Cause:** Server can't reach `https://www.googleapis.com/oauth2/v3/certs`

**Fix:**
- Check firewall rules
- Verify outbound HTTPS is allowed
- Test: `curl https://www.googleapis.com/oauth2/v3/certs`

## 5. Verification Checklist

Run this in Frappe console after publishing test message:

```python
import frappe

# Get recent webhook logs
logs = frappe.get_all('Error Log',
    filters={'error': ['like', '%JWT%']},
    fields=['creation', 'error'],
    order_by='creation desc',
    limit=5
)

for log in logs:
    print(f"{log.creation}:")
    print(log.error[:200])
    print()
```

**Expected output with JWT:**
```
2026-03-22 18:40:00:
🔑 JWT Token Received
Token length: 850 characters
...
```

## 6. Security Notes

### With JWT Authentication (Recommended)
- ✅ Requests are authenticated
- ✅ Only Google can call webhook
- ✅ Tokens are verified cryptographically
- ✅ Production-ready

### Without JWT Authentication (Current - Temporary)
- ⚠️ Requests are NOT authenticated
- ⚠️ Anyone can call webhook
- ⚠️ No verification
- ❌ NOT production-ready

## 7. Current Webhook Behavior

The webhook currently has **optional JWT verification**:

- If JWT token present → Verifies it
- If JWT token missing → Logs warning but continues
- This allows testing without authentication
- **Should be made mandatory for production**

### To Make JWT Mandatory

Edit `google_meet_events.py`:

```python
# Change this:
if not auth_header.startswith('Bearer '):
    frappe.log_error(...)
    # Continue without JWT verification

# To this:
if not auth_header.startswith('Bearer '):
    frappe.log_error(...)
    return {"status": "error", "message": "Unauthorized"}, 401
```

## 8. Final Verification

After configuring service account authentication:

1. ✅ Publish test message from Google Cloud Console
2. ✅ Check Error Log shows "JWT Token Received"
3. ✅ Check Error Log shows "JWT Verified Successfully"
4. ✅ Check Error Log shows event processing logs
5. ✅ Verify meeting record is updated

If all checks pass, JWT authentication is working correctly!

---

**Created:** March 22, 2026  
**Related:** PUBSUB_JWT_AUTHENTICATION.md, WEBHOOK_TROUBLESHOOTING.md
