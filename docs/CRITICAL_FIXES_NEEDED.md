# Critical Issues to Fix

## Issue 1: Pub/Sub Push Endpoint Not Configured ⚠️ CRITICAL

**Problem:**
- We have webhook handler code: `handle_pubsub_push()`
- But Pub/Sub subscription is using PULL delivery, not PUSH
- Google is NOT sending events to our webhook
- Events are sitting in Pub/Sub waiting to be pulled

**Current State:**
- Topic: `projects/rounds-288112/topics/meet-events` ✓ Created
- Subscription: `meet-events-sub` ✓ Created (default with topic)
- Delivery Type: **PULL** ❌ Wrong!
- Webhook: Code exists but not being called

**Fix Required in Google Cloud Console:**

1. Go to: https://console.cloud.google.com/cloudpubsub/subscription/list
2. Click on subscription: `meet-events-sub`
3. Click **EDIT** button
4. Under **Delivery type**:
   - Change from: **Pull**
   - Change to: **Push**
5. **Endpoint URL**: 
   ```
   https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push
   ```
6. Click **UPDATE**

**Verification:**
After configuring push:
1. Create a VidCon Meeting
2. Join the meeting
3. Check VidCon Event Log - events should appear within seconds
4. If no events, check Error Log for webhook errors

**Why This Happened:**
- Google's tutorial uses PULL (they poll for events in code)
- We implemented PUSH (webhook) but never configured the subscription
- The `gcloud pubsub topics create` command creates a PULL subscription by default

---

## Issue 2: VidCon Event Log Link in Workspace ✓ ALREADY FIXED

**Status:** VidCon Event Log is already in the workspace shortcuts.

**Access:**
- Press Ctrl+K → type "VidCon Event Log"
- Or click VidCon workspace → VidCon Event Log shortcut

---

## Issue 3: Calendar Deletion Not Syncing to Google ⚠️ NEEDS FIX

**Problem:**
- When VidCon Meeting is deleted, the Google Calendar Event is not deleted
- Event remains on Google Calendar
- Meet link still works

**Current Code:**
- No `on_trash()` method in VidConMeeting
- No cleanup of Google Calendar Event
- No deletion of Meet Events subscription

**Fix Required:**

Add to `vidcon_meeting.py`:

```python
def on_trash(self):
    """Clean up Google Calendar Event and Meet subscription when meeting is deleted"""
    # Delete Google Calendar Event
    if self.event:
        try:
            event_doc = frappe.get_doc("Event", self.event)
            event_doc.delete(ignore_permissions=True)
            frappe.logger().info(f"Deleted Event {self.event} for meeting {self.name}")
        except Exception as e:
            frappe.log_error(f"Error deleting Event {self.event}: {str(e)}")
    
    # Delete Meet Events subscription
    if self.meet_subscription_id:
        try:
            from vidcon.vidcon.doctype.vidcon_meeting.meet_utils import delete_space_subscription
            delete_space_subscription(self.meet_subscription_id)
            frappe.logger().info(f"Deleted subscription {self.meet_subscription_id} for meeting {self.name}")
        except Exception as e:
            frappe.log_error(f"Error deleting subscription {self.meet_subscription_id}: {str(e)}")
```

**Verification:**
1. Create a VidCon Meeting
2. Note the Event name and Meet link
3. Delete the VidCon Meeting
4. Check that Event is deleted
5. Check that Meet link returns 404 or "meeting not found"

---

## Priority Order

1. **CRITICAL - Issue 1**: Configure Pub/Sub push endpoint
   - Without this, NO events will be received
   - This is blocking all event functionality

2. **HIGH - Issue 3**: Fix calendar deletion sync
   - Creates orphaned events and meetings
   - Confusing for users

3. **DONE - Issue 2**: Event Log workspace link
   - Already implemented

---

## Testing Checklist

After fixing Issue 1 (Pub/Sub push):

- [ ] Create VidCon Meeting
- [ ] Wait for Meet link to be populated
- [ ] Join the meeting
- [ ] Check VidCon Event Log for `conference.v2.started` event
- [ ] Check for `participant.v2.joined` event
- [ ] Leave the meeting
- [ ] Check for `participant.v2.left` event
- [ ] Check for `conference.v2.ended` event (when last person leaves)

After fixing Issue 3 (deletion sync):

- [ ] Create VidCon Meeting
- [ ] Note the Event name
- [ ] Delete VidCon Meeting
- [ ] Verify Event is deleted from Event list
- [ ] Verify Meet link no longer works
- [ ] Verify subscription is deleted (check Google Cloud Console)

---

## Current Architecture

**Event Flow (when working):**

```
1. User joins Meet
   ↓
2. Google Meet detects event
   ↓
3. Google Workspace Events API publishes to Pub/Sub topic
   ↓
4. Pub/Sub PUSHES to webhook (IF CONFIGURED)
   ↓
5. handle_pubsub_push() receives POST request
   ↓
6. Event logged to VidCon Event Log
   ↓
7. Event processed (update meeting status, etc.)
```

**Current Broken Point:**
Step 4 - Pub/Sub is NOT pushing because subscription is set to PULL mode.

---

## Documentation to Update

After fixes:

1. PRODUCTION_DEPLOYMENT.md
   - Add Pub/Sub push configuration step
   - Add verification steps

2. GOOGLE_WORKSPACE_SETUP.md
   - Add push subscription configuration
   - Clarify PULL vs PUSH difference

3. README.md
   - Add troubleshooting section for "no events received"
