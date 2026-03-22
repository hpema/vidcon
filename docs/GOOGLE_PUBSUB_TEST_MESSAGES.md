# Google Cloud Console - Test Message Structures

**Purpose:** Message structures for testing Pub/Sub push subscriptions using Google Cloud Console

## How to Test in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **Pub/Sub** → **Topics**
3. Click on your topic (e.g., `meet-events`)
4. Click **PUBLISH MESSAGE** button
5. Paste one of the message structures below
6. Click **Publish**

## Message Structure for Conference Ended

### Attributes (Key-Value Pairs)

Add these in the **Attributes** section:

| Key | Value |
|-----|-------|
| `ce-type` | `google.workspace.meet.conference.v2.ended` |
| `ce-source` | `//meet.googleapis.com/spaces/yqb-makz-vwf` |
| `ce-subject` | `conferenceRecords/test-conference-123` |
| `ce-id` | `test-event-123` |

### Message Body

Paste this in the **Message body** field:

```json
{
  "conferenceRecord": {
    "name": "conferenceRecords/test-conference-123",
    "space": "spaces/yqb-makz-vwf",
    "startTime": "2026-03-22T13:00:00Z",
    "endTime": "2026-03-22T14:00:00Z"
  }
}
```

**Note:** Replace `yqb-makz-vwf` with your actual meeting's space ID

## Message Structure for Conference Started

### Attributes

| Key | Value |
|-----|-------|
| `ce-type` | `google.workspace.meet.conference.v2.started` |
| `ce-source` | `//meet.googleapis.com/spaces/yqb-makz-vwf` |
| `ce-subject` | `conferenceRecords/test-conference-123` |
| `ce-id` | `test-event-124` |

### Message Body

```json
{
  "conferenceRecord": {
    "name": "conferenceRecords/test-conference-123",
    "space": "spaces/yqb-makz-vwf",
    "startTime": "2026-03-22T13:00:00Z"
  }
}
```

## Message Structure for Transcript Ready

### Attributes

| Key | Value |
|-----|-------|
| `ce-type` | `google.workspace.meet.transcript.v2.fileGenerated` |
| `ce-source` | `//meet.googleapis.com/conferenceRecords/test-conference-123` |
| `ce-subject` | `conferenceRecords/test-conference-123/transcripts/transcript-456` |
| `ce-id` | `test-event-125` |

### Message Body

```json
{
  "transcript": {
    "name": "conferenceRecords/test-conference-123/transcripts/transcript-456",
    "conferenceRecord": "conferenceRecords/test-conference-123",
    "state": "ENDED",
    "driveDestination": {
      "file": "files/1234567890abcdef",
      "exportUri": "https://drive.google.com/file/d/1234567890abcdef/view"
    }
  }
}
```

## What Happens When You Publish

1. Message is published to the Pub/Sub topic
2. Pub/Sub pushes it to your webhook endpoint
3. Your webhook receives it and processes it
4. You'll see logs in Error Log

## Expected Logs in Frappe

After publishing a test message, check **Error Log** for:

1. 🔔 **Pub/Sub Webhook Called**
2. 📋 **Request Headers**
3. 📦 **Raw Request Body**
4. 📨 **Decoded Event Data**
5. 🏷️ **Event Attributes**
6. 🎯 **Event Type Extracted**
7. 🏁 **Processing: conference.ended** (or other event type)
8. ✅ **Webhook Processing Complete**

## Important Notes

### JWT Token

When you publish via Google Cloud Console, the message will be pushed to your webhook **with a valid Google-signed JWT token**. This means:
- ✅ JWT verification will pass
- ✅ Full event processing will occur
- ✅ You'll see the complete flow

This is different from curl testing where we can't generate valid JWT tokens.

### Space ID

Make sure to use your actual meeting's `google_space_id`:
- Open your VidCon Meeting
- Copy the value from `google_space_id` field
- Replace `yqb-makz-vwf` in the examples above

### Conference ID

The `conferenceRecord.name` should match the pattern:
- Format: `conferenceRecords/{conference-id}`
- Example: `conferenceRecords/test-conference-123`

For real testing, use the actual conference ID if you have it, or use a test value.

## Testing Different Event Types

### Test 1: Conference Started
1. Publish "Conference Started" message
2. Check Error Log
3. Verify meeting status changes to "In Progress"

### Test 2: Conference Ended
1. Publish "Conference Ended" message
2. Check Error Log
3. Verify meeting status changes to "Completed"

### Test 3: Transcript Ready
1. Publish "Transcript Ready" message
2. Check Error Log
3. Verify transcript download is attempted

## Troubleshooting

### No logs appear in Error Log

**Check:**
1. Push subscription exists and is active
2. Endpoint URL is correct in subscription
3. Webhook endpoint is accessible (test with curl)
4. Check Google Cloud Logging for delivery errors

### Logs appear but event not processed

**Check:**
1. Space ID matches your meeting's `google_space_id`
2. Event type is spelled correctly in attributes
3. Message body JSON is valid
4. Check Error Log for handler errors

### JWT verification fails

**This shouldn't happen when publishing via Google Cloud Console** because Google signs the JWT. If it does:
1. Check your site URL is correct
2. Verify webhook endpoint URL matches expected audience
3. Check Error Log for JWT verification details

## Complete Test Flow

### Step-by-Step Test

1. **Prepare:**
   - Open your VidCon Meeting
   - Note the `google_space_id` value
   - Ensure `meet_subscription_id` is set

2. **Publish Conference Started:**
   - Go to Google Cloud Console → Pub/Sub → Topics
   - Click your topic → PUBLISH MESSAGE
   - Add attributes (see above)
   - Paste message body with your space ID
   - Click Publish

3. **Verify in Frappe:**
   - Go to Error Log
   - Look for "🔔 Pub/Sub Webhook Called"
   - Check meeting status changed to "In Progress"

4. **Publish Conference Ended:**
   - Same process, use "Conference Ended" message
   - Verify status changes to "Completed"

5. **Publish Transcript Ready:**
   - Use "Transcript Ready" message
   - Verify transcript download attempted

## Expected Results

### Conference Started Event
- ✅ Webhook receives event
- ✅ Meeting status → "In Progress"
- ✅ `google_conference_id` set (if not already)
- ✅ `actual_start_time` set

### Conference Ended Event
- ✅ Webhook receives event
- ✅ Meeting status → "Completed"
- ✅ `actual_end_time` set

### Transcript Ready Event
- ✅ Webhook receives event
- ✅ Transcript download attempted
- ⚠️ May fail if transcript file doesn't exist (expected for test data)
- ✅ Status → "Transcript Retrieved" (if download succeeds)

---

**Created:** March 22, 2026  
**Related:** VIEWING_WEBHOOK_LOGS.md, WEBHOOK_TROUBLESHOOTING.md
