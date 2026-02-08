# VidCon Meet Events - Diagnostic Checklist

## Current Issues Reported

1. ❌ No events appearing in VidCon Event Log after joining meeting
2. ❌ Gemini notes not enabled by default in meetings
3. ❌ Transcripts not being captured/stored in VidCon Meeting
4. ❌ Different Meet link in calendar vs VidCon

---

## Issue 1: No Events in Event Log (CRITICAL)

**Root Cause:** Pub/Sub subscription is NOT configured for PUSH delivery.

### Verification Steps

**Step 1: Check Pub/Sub Subscription Configuration**

Go to: https://console.cloud.google.com/cloudpubsub/subscription/list

Find subscription: `meet-events-sub`

Check:
- [ ] Delivery type is **Push** (not Pull)
- [ ] Push endpoint is: `https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`
- [ ] Subscription state is **Active**

**If Delivery type is Pull:**
1. Click subscription name
2. Click **EDIT**
3. Change **Delivery type** to **Push**
4. Set **Endpoint URL**: `https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`
5. Click **UPDATE**

**Step 2: Test Webhook Endpoint**

Run this command to test if webhook is accessible:

```bash
curl -X POST https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "data": "dGVzdA==",
      "messageId": "test123",
      "publishTime": "2024-01-01T00:00:00Z"
    }
  }'
```

Expected: HTTP 200 response (even if data is invalid, endpoint should respond)

**Step 3: Check VidCon Meeting Has Subscription**

```bash
bench --site YOUR_SITE console
```

```python
import frappe
meetings = frappe.get_all("VidCon Meeting", 
    fields=["name", "google_meet_link", "meet_subscription_id"],
    limit=5)
for m in meetings:
    print(f"{m.name}: {m.meet_subscription_id}")
```

Expected: Each meeting should have a `meet_subscription_id` like `subscriptions/abc123...`

**Step 4: Verify Subscription in Google**

```bash
bench --site YOUR_SITE console
```

```python
import frappe
from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import get_subscription_status

settings = frappe.get_single("VidCon Settings")
meeting = frappe.get_last_doc("VidCon Meeting")

if meeting.meet_subscription_id:
    status = get_subscription_status(
        google_calendar_name=settings.google_calendar,
        subscription_id=meeting.meet_subscription_id
    )
    print(f"Subscription state: {status.get('state')}")
    print(f"Target resource: {status.get('targetResource')}")
else:
    print("No subscription ID on meeting")
```

Expected: State should be `ACTIVE`

**Step 5: Check Error Log**

Go to: Error Log (Ctrl+K → Error Log)

Look for:
- "VidCon Token Refresh Failed"
- "Meet Subscription Creation Failed"
- "Pub/Sub push handler error"

---

## Issue 2: Gemini Notes Not Enabled

**Root Cause:** Google Calendar API doesn't support enabling Gemini notes programmatically.

### Current Behavior

When VidCon creates a meeting via Calendar API:
- Basic Meet link is created
- Gemini notes are NOT enabled
- User must manually enable in Meet UI

### Workaround

**Option 1: Manual Enable (Current)**
1. Join the meeting
2. Click "Activities" → "Take notes for me"
3. Gemini will start taking notes

**Option 2: Use Google Workspace Admin Settings**
- Admin can set Gemini notes as default for organization
- Go to: Google Admin Console → Apps → Google Meet → Meet settings
- Enable "Take meeting notes" by default

**Option 3: Different Meet Link Creation (Not Recommended)**
- Use Meet API directly instead of Calendar API
- More complex, requires different OAuth flow

### Why Calendar Link Looks Different

**VidCon-created link:**
- Format: `https://meet.google.com/abc-defg-hij`
- Basic Meet space
- No Gemini enabled

**Calendar UI-created link:**
- Same format but may have additional metadata
- Can have Gemini pre-enabled if you selected it
- May show as "scheduled" vs "instant"

---

## Issue 3: Transcripts Not Being Captured

**Root Cause:** Multiple potential issues.

### Verification Steps

**Step 1: Check if Transcript Events Are Subscribed**

```bash
bench --site YOUR_SITE console
```

```python
import frappe
from vidcon.vidcon.doctype.vidcon_meeting.subscription_manager import get_subscription_status

settings = frappe.get_single("VidCon Settings")
meeting = frappe.get_last_doc("VidCon Meeting")

status = get_subscription_status(
    google_calendar_name=settings.google_calendar,
    subscription_id=meeting.meet_subscription_id
)

event_types = status.get('eventTypes', [])
print("Subscribed event types:")
for et in event_types:
    print(f"  - {et}")

# Should include:
# - google.workspace.meet.transcript.v2.fileGenerated
```

**Step 2: Check VidCon Event Log for Transcript Events**

Go to: VidCon Event Log

Filter by:
- Event Type = "google.workspace.meet.transcript.v2.fileGenerated"

If no events:
- Pub/Sub push is not configured (see Issue 1)
- OR transcript was not generated (Gemini not enabled)

**Step 3: Check if Transcript Handler is Working**

Look in Error Log for:
- "Transcript Ready Handler Error"
- "Error downloading transcript"

**Step 4: Verify Drive Access**

The transcript is stored in Google Drive. Check:
- OAuth scopes include `drive.readonly`
- User has access to the Drive file

### Required OAuth Scopes for Transcripts

```
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/meetings.space.readonly
https://www.googleapis.com/auth/drive.readonly  ← Required for transcripts
```

Verify in VidCon Settings → Authorize Google Calendar (VidCon) includes all three.

---

## Complete Test Flow

### Test 1: Create Meeting and Verify Subscription

```bash
# 1. Create meeting via UI
# 2. Wait 10 seconds for background job

bench --site YOUR_SITE console
```

```python
import frappe

meeting = frappe.get_last_doc("VidCon Meeting")
print(f"Meeting: {meeting.name}")
print(f"Meet Link: {meeting.google_meet_link}")
print(f"Space ID: {meeting.google_space_id}")
print(f"Subscription ID: {meeting.meet_subscription_id}")

# Should all be populated
```

### Test 2: Join Meeting and Check Events

```bash
# 1. Join the meeting via the Meet link
# 2. Wait 30 seconds
# 3. Leave the meeting
# 4. Check Event Log

bench --site YOUR_SITE console
```

```python
import frappe

events = frappe.get_all("VidCon Event Log",
    fields=["name", "event_type", "received_at", "status"],
    order_by="received_at desc",
    limit=10)

for e in events:
    print(f"{e.received_at}: {e.event_type} - {e.status}")

# Expected events:
# - google.workspace.meet.conference.v2.started
# - google.workspace.meet.participant.v2.joined
# - google.workspace.meet.participant.v2.left
# - google.workspace.meet.conference.v2.ended
```

### Test 3: Enable Gemini and Check Transcript

```bash
# 1. Create new meeting
# 2. Join meeting
# 3. Enable "Take notes for me" in Meet
# 4. Say something (at least 30 seconds of speech)
# 5. Leave meeting
# 6. Wait 5 minutes for transcript processing
# 7. Check Event Log

bench --site YOUR_SITE console
```

```python
import frappe

# Check for transcript event
transcript_events = frappe.get_all("VidCon Event Log",
    filters={"event_type": "google.workspace.meet.transcript.v2.fileGenerated"},
    fields=["name", "received_at", "raw_payload"],
    order_by="received_at desc",
    limit=1)

if transcript_events:
    print("Transcript event received!")
    print(transcript_events[0])
else:
    print("No transcript events yet")

# Check if transcript stored on meeting
meeting = frappe.get_last_doc("VidCon Meeting")
print(f"Transcript: {meeting.transcript}")
print(f"Transcript File ID: {meeting.transcript_file_id}")
```

---

## Quick Fixes

### Fix 1: Configure Pub/Sub Push (REQUIRED)

```bash
# Cannot be done via code - must use Google Cloud Console
# See Issue 1 verification steps above
```

### Fix 2: Re-authorize with All Scopes

If transcript events arrive but download fails:

1. Go to VidCon Settings
2. Click Actions → "Authorize Google Calendar (VidCon)"
3. Verify consent screen shows:
   - Calendar access ✓
   - Meet conference access ✓
   - Drive file access ✓
4. Click Allow

### Fix 3: Check Webhook Logs

```bash
# Check if webhook is being called
tail -f ~/frappe-bench/sites/YOUR_SITE/logs/web.log | grep handle_pubsub_push
```

During a meeting, you should see POST requests to the webhook.

---

## Expected Timeline

**Meeting Creation:**
- 0s: User creates VidCon Meeting
- 2s: Google Calendar Event created
- 5s: Meet link fetched from Google
- 7s: Subscription created for space
- 10s: Meeting ready

**During Meeting:**
- User joins: `conference.v2.started` event (within 10s)
- User joins: `participant.v2.joined` event (within 10s)
- User leaves: `participant.v2.left` event (within 10s)
- Last user leaves: `conference.v2.ended` event (within 10s)

**After Meeting (with Gemini):**
- 2-5 minutes: Transcript generated
- `transcript.v2.fileGenerated` event received
- Transcript downloaded from Drive
- Stored in VidCon Meeting

---

## Common Issues

### "No events in Event Log"
→ Pub/Sub push not configured (Issue 1)

### "Events appear but not linked to meeting"
→ Space ID mismatch or conference ID not stored

### "Transcript event received but not stored"
→ Drive access issue or handler error (check Error Log)

### "Different Meet link in calendar"
→ Expected - Calendar may show additional metadata but link works the same

### "Gemini not enabled by default"
→ Expected - must enable manually or via Workspace admin settings
