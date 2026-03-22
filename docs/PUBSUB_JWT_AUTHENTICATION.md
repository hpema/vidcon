# Pub/Sub Push Subscription - JWT Authentication Setup

**Issue:** Google is calling webhook but NOT sending JWT tokens (Authorization header is EMPTY)

## The Problem

Your logs show:
```
Authorization header: EMPTY
```

This means Google Pub/Sub is sending requests **without authentication**, which causes the webhook to reject them.

## Why This Happens

By default, Pub/Sub push subscriptions send requests **without authentication**. You must explicitly configure authentication when creating the push subscription.

## Solution: Configure Push Subscription with JWT Authentication

### Option 1: Update Existing Subscription (Recommended)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **Pub/Sub** → **Subscriptions**
3. Click on your push subscription (e.g., `meet-events-push`)
4. Click **EDIT** at the top
5. Scroll to **Authentication** section
6. Select **Service account**
7. Choose the service account (or use default Compute Engine service account)
8. Click **UPDATE**

### Option 2: Create New Subscription with Authentication

1. Go to **Pub/Sub** → **Subscriptions**
2. Click **CREATE SUBSCRIPTION**
3. **Subscription ID:** `meet-events-push-authenticated`
4. **Select a Cloud Pub/Sub topic:** Your topic (e.g., `meet-events`)
5. **Delivery type:** Push
6. **Endpoint URL:** `https://dev.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`
7. **Authentication:**
   - Select **Service account**
   - Choose service account (or use default)
8. Click **CREATE**

### Option 3: Temporary - Disable JWT Verification for Testing

If you want to test immediately without reconfiguring Pub/Sub, you can temporarily disable JWT verification in the webhook.

**WARNING:** This is insecure and should only be used for testing!

## How JWT Authentication Works

When properly configured:

1. Google signs each request with a JWT token
2. JWT is sent in `Authorization: Bearer <token>` header
3. Your webhook verifies the JWT signature using Google's public keys
4. If valid, request is processed
5. If invalid, request is rejected

## Current State

Your webhook logs show Google IS calling the endpoint, but:
- ❌ No JWT token in Authorization header
- ❌ Webhook rejects requests (returns 401)
- ❌ Google retries constantly (exponential backoff)

## After Fixing

Once authentication is configured:
- ✅ JWT token in Authorization header
- ✅ Webhook verifies JWT
- ✅ Events are processed
- ✅ No more constant retries

## Verify Authentication is Configured

After updating the subscription, trigger a test event and check logs:

```python
# In Frappe console
import frappe
logs = frappe.get_all('Error Log',
    filters={'error': ['like', '%Authorization header%']},
    fields=['creation', 'error'],
    order_by='creation desc',
    limit=1
)

if logs:
    print(logs[0].error)
```

Should show:
```
Authorization header: Bearer eyJhbGc...
```

Instead of:
```
Authorization header: EMPTY
```

---

**Created:** March 22, 2026  
**Related:** WEBHOOK_TROUBLESHOOTING.md, VIEWING_WEBHOOK_LOGS.md
