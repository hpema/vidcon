# Viewing Webhook Logs - Complete Guide

**Updated:** March 22, 2026  
**Purpose:** Comprehensive logging added to diagnose Pub/Sub webhook issues

## What's Been Added

The webhook handler now logs **every step** of the process to Frappe's Error Log for easy visibility.

## How to View Logs

### Method 1: Error Log List (Easiest)

1. In Frappe, go to **Error Log** list
2. You'll see entries with emoji icons for easy identification:

**Webhook Activity:**
- 🔔 **Pub/Sub Webhook Called** - Webhook endpoint was hit
- 📋 **Request Headers** - All HTTP headers from Google
- 📦 **Raw Request Body** - Complete request payload
- 🔑 **JWT Token Received** - Authentication token details
- 🎯 **Verifying JWT Audience** - Token validation
- ✅ **JWT Verified Successfully** - Authentication passed
- ❌ **JWT Verification Failed** - Authentication failed

**Event Processing:**
- 📨 **Decoded Event Data** - Parsed event content
- 🏷️ **Event Attributes** - CloudEvents metadata
- 🎯 **Event Type Extracted** - Which event type was detected
- 🆔 **Event Identifiers** - Event ID, subscription ID

**Event Handlers:**
- 🚀 **Processing: conference.started** - Meeting started
- 🏁 **Processing: conference.ended** - Meeting ended
- 👤 **Processing: participant.joined** - Someone joined
- 👋 **Processing: participant.left** - Someone left
- 🎥 **Processing: recording.fileGenerated** - Recording ready
- 📝 **Processing: transcript.fileGenerated** - Transcript ready
- ⚠️ **Unhandled Event Type** - Unknown event received

**Completion:**
- ✅ **Webhook Processing Complete** - Successfully processed

### Method 2: Filter by Time

```python
# In Frappe console
frappe.get_all("Error Log",
    filters={
        "creation": [">", "2026-03-22 16:00:00"]  # Adjust time
    },
    fields=["creation", "error", "method"],
    order_by="creation desc",
    limit=50
)
```

### Method 3: Filter by Title Pattern

```python
# Show only webhook calls
frappe.get_all("Error Log",
    filters={
        "error": ["like", "%Pub/Sub Webhook Called%"]
    },
    fields=["creation", "error"],
    order_by="creation desc",
    limit=20
)
```

### Method 4: Search for Specific Event Type

```python
# Find conference.ended events
frappe.get_all("Error Log",
    filters={
        "error": ["like", "%conference.ended%"]
    },
    fields=["creation", "error"],
    order_by="creation desc"
)
```

## What Each Log Shows

### 🔔 Pub/Sub Webhook Called
```
Webhook endpoint hit at 2026-03-22T16:30:00
Method: POST
Path: /api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push
```

**What this tells you:**
- ✅ Google IS calling your webhook
- ❌ If missing: Google can't reach your server

### 📋 Request Headers
```json
{
  "Authorization": "Bearer eyJhbGc...",
  "Content-Type": "application/json",
  "User-Agent": "APIs-Google; (+https://developers.google.com/webmasters/APIs-Google.html)"
}
```

**What this tells you:**
- ✅ JWT token is present
- ✅ Request is from Google (User-Agent)

### 📦 Raw Request Body
```
Body length: 1234 bytes

{
  "message": {
    "data": "eyJjb25mZXJlbmNlUmVjb3JkIjp7Im5hbWUiOi...",
    "attributes": {
      "ce-type": "google.workspace.meet.conference.v2.ended"
    }
  }
}
```

**What this tells you:**
- ✅ Message structure is correct
- ✅ Event type is in attributes

### 📨 Decoded Event Data
```json
{
  "conferenceRecord": {
    "name": "conferenceRecords/abc-123-def",
    "space": "spaces/xyz-abcd-efg",
    "startTime": "2026-03-22T16:00:00Z",
    "endTime": "2026-03-22T16:30:00Z"
  }
}
```

**What this tells you:**
- ✅ Event data decoded successfully
- ✅ Contains conference details
- ✅ Has space ID for matching

### 🎯 Event Type Extracted
```
Event Type: 'google.workspace.meet.conference.v2.ended'
Length: 47
Source: //meet.googleapis.com/...
```

**What this tells you:**
- ✅ Event type parsed correctly
- ✅ Event source is Google Meet

### 🏁 Processing: conference.ended
```
Calling handle_conference_ended()
```

**What this tells you:**
- ✅ Correct handler being called
- ✅ Event routing working

### ✅ Webhook Processing Complete
```
Event type 'google.workspace.meet.conference.v2.ended' processed successfully
Returning status: ok
```

**What this tells you:**
- ✅ No errors during processing
- ✅ Webhook returned 200 OK to Google

## Diagnostic Scenarios

### Scenario 1: No Logs at All

**Symptom:** No "Pub/Sub Webhook Called" logs

**Diagnosis:**
- ❌ Google is NOT calling your webhook
- ❌ Pub/Sub subscription not configured correctly
- ❌ Webhook URL is wrong
- ❌ Firewall blocking requests

**Fix:**
1. Check Google Cloud Console → Pub/Sub → Subscriptions
2. Verify endpoint URL is correct
3. Check for delivery errors in Pub/Sub metrics
4. Test endpoint with curl

### Scenario 2: Webhook Called But JWT Failed

**Symptom:** 
- ✅ "Pub/Sub Webhook Called" logs
- ❌ "JWT Verification Failed" logs

**Diagnosis:**
- ❌ JWT token invalid or expired
- ❌ Audience mismatch
- ❌ Google's public keys not accessible

**Fix:**
1. Check Error Log for JWT verification details
2. Verify site URL is correct
3. Check internet connectivity for fetching Google's public keys

### Scenario 3: Event Type Not Extracted

**Symptom:**
- ✅ Webhook called and JWT verified
- ⚠️ Event type is empty string

**Diagnosis:**
- ❌ Event format unexpected
- ❌ Attributes missing ce-type

**Fix:**
1. Check "Event Attributes" log
2. Verify event structure in "Decoded Event Data"
3. May need to adjust event type extraction logic

### Scenario 4: Unhandled Event Type

**Symptom:**
- ⚠️ "Unhandled Event Type" log

**Diagnosis:**
- ℹ️ Event type not in our handler list
- ℹ️ Could be a new event type from Google

**Fix:**
1. Check the event type in the log
2. If it's a valid Meet event, add handler
3. If it's noise, can ignore

### Scenario 5: Handler Called But No Update

**Symptom:**
- ✅ "Processing: conference.ended" log
- ✅ "Webhook Processing Complete" log
- ❌ Meeting status not updated

**Diagnosis:**
- ❌ Handler can't find meeting
- ❌ space_id mismatch
- ❌ conference_id not set

**Fix:**
1. Check handler logs (handle_conference_ended)
2. Look for "No meetings found" messages
3. Use "Sync from Google Meet" button

## Real-Time Monitoring

### Watch Logs Live (Console)

```python
# In Frappe console
import time
last_check = frappe.utils.now_datetime()

while True:
    logs = frappe.get_all("Error Log",
        filters={"creation": [">", last_check]},
        fields=["creation", "error"],
        order_by="creation asc"
    )
    
    for log in logs:
        print(f"\n[{log.creation}]")
        print(log.error[:200])
        last_check = log.creation
    
    time.sleep(5)  # Check every 5 seconds
```

### Count Events by Type

```python
# Count how many of each event type received
from collections import Counter

logs = frappe.get_all("Error Log",
    filters={
        "error": ["like", "%Processing:%"],
        "creation": [">", "2026-03-22"]
    },
    fields=["error"]
)

event_types = []
for log in logs:
    if "conference.started" in log.error:
        event_types.append("started")
    elif "conference.ended" in log.error:
        event_types.append("ended")
    elif "participant.joined" in log.error:
        event_types.append("joined")
    elif "participant.left" in log.error:
        event_types.append("left")
    elif "transcript.fileGenerated" in log.error:
        event_types.append("transcript")

Counter(event_types)
```

## Testing the Logging

### Trigger a Test Event

1. Create a VidCon Meeting
2. Join the Google Meet
3. End the meeting
4. Check Error Logs immediately

**Expected logs (in order):**
1. 🔔 Webhook Called (when you join)
2. 🚀 Processing: conference.started
3. ✅ Processing Complete
4. 🔔 Webhook Called (when you leave)
5. 🏁 Processing: conference.ended
6. ✅ Processing Complete

### Manual Webhook Test

```bash
# Test your webhook endpoint
curl -X POST https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{
    "message": {
      "data": "eyJ0ZXN0IjogInRlc3QifQ==",
      "attributes": {"ce-type": "test"},
      "messageId": "test-123"
    }
  }'
```

**Expected logs:**
- 🔔 Webhook Called
- ❌ JWT Verification Failed (expected - test token)

## Cleanup Old Logs

```python
# Delete logs older than 7 days
frappe.db.sql("""
    DELETE FROM `tabError Log`
    WHERE creation < DATE_SUB(NOW(), INTERVAL 7 DAY)
    AND error LIKE '%Pub/Sub%'
""")
frappe.db.commit()
```

## Quick Reference

**View recent webhook activity:**
```python
frappe.get_all("Error Log",
    filters={"error": ["like", "%Webhook Called%"]},
    fields=["creation", "error"],
    order_by="creation desc",
    limit=10
)
```

**View recent event processing:**
```python
frappe.get_all("Error Log",
    filters={"error": ["like", "%Processing:%"]},
    fields=["creation", "error"],
    order_by="creation desc",
    limit=10
)
```

**View errors only:**
```python
frappe.get_all("Error Log",
    filters={"error": ["like", "%❌%"]},
    fields=["creation", "error"],
    order_by="creation desc",
    limit=10
)
```

---

**Created:** March 22, 2026  
**Related:** WEBHOOK_TROUBLESHOOTING.md, MEETING_STATUS_FIX.md
