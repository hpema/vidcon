# Google Meet Subscription Flow - Explained

**Updated:** March 22, 2026  
**Purpose:** Clarify how subscriptions work and when they're needed

## The Correct Flow

### 1. Meeting Creation
```
User creates VidCon Meeting
    ↓
Google Calendar event created
    ↓
Google Meet link generated
    ↓
google_space_id extracted and stored
```

**At this point:** Meeting exists but NO subscription yet

### 2. Subscription Creation (Manual)
```
User clicks "Create Meet Subscription" button
    ↓
Subscription created for spaces/{google_space_id}
    ↓
meet_subscription_id stored on meeting
    ↓
Google will now send events to Pub/Sub topic
```

**At this point:** Subscription active, events will be sent

### 3. Meeting Lifecycle (Automatic)
```
Someone joins meeting
    ↓
Google sends conference.started event to Pub/Sub
    ↓
Pub/Sub pushes to webhook
    ↓
Webhook updates meeting status to "In Progress"
    ↓
Meeting ends
    ↓
Google sends conference.ended event
    ↓
Webhook updates status to "Completed"
    ↓
Transcript ready (10-15 min later)
    ↓
Google sends transcript.fileGenerated event
    ↓
Webhook downloads transcript
```

## Do You Need Subscriptions?

### YES - If you want automatic updates:
- ✅ Meeting status changes (In Progress → Completed)
- ✅ Automatic transcript download
- ✅ Real-time participant tracking
- ✅ Recording notifications

### NO - If you're okay with manual sync:
- ❌ Use "Sync from Google Meet" button instead
- ❌ Manually fetch transcripts
- ❌ No real-time updates

## Two Approaches

### Approach 1: Automatic (Recommended for Production)

**Setup:**
1. Configure Pub/Sub topic in Google Cloud Console
2. Set up push subscription to your webhook
3. Enable Meet Events in VidCon Settings
4. Set Pub/Sub topic name in VidCon Settings

**Per Meeting:**
1. Create meeting (automatic)
2. Click "Create Meet Subscription" button (manual, once per meeting)
3. Everything else is automatic

**Pros:**
- Real-time updates
- No manual intervention needed
- Transcript auto-downloaded

**Cons:**
- Requires Pub/Sub setup
- One subscription per meeting
- More complex infrastructure

### Approach 2: Manual Sync (Simpler)

**Setup:**
1. Just configure Google Calendar
2. No Pub/Sub needed

**Per Meeting:**
1. Create meeting (automatic)
2. After meeting ends, click "Sync from Google Meet" (manual)
3. Transcript fetched on demand

**Pros:**
- Simpler setup
- No subscriptions needed
- Works for old meetings

**Cons:**
- Manual intervention required
- No real-time updates
- Have to remember to sync

## Why Per-Meeting Subscriptions?

**Q: Why not one global subscription for all meetings?**

A: Google Workspace Events API works on a **resource-based** model:
- Each subscription monitors ONE space (meeting room)
- You subscribe to `spaces/{space_id}` not to "all meetings"
- This is how Google designed the API

**Alternative (not currently implemented):**
- Subscribe to user-level events (all meetings for a user)
- But this requires different event types and filtering

## Current Implementation

### What Happens on Meeting Creation

**File:** `vidcon_meeting.py` → `after_insert()`

```python
def after_insert(self):
    # Create Google Calendar event
    self.create_google_calendar_event()
    
    # Extract and store space_id
    if self.google_meet_link:
        space_id = extract_space_id_from_meet_link(self.google_meet_link)
        self.db_set("google_space_id", space_id)
    
    # Subscription is NOT created automatically
    # User must click "Create Meet Subscription" button
```

**Why not automatic?**
- Subscriptions have quotas/limits
- Not all meetings need subscriptions
- User might want manual control

### What the Button Does

**Button:** "Create Meet Subscription" in Actions menu

**Code:** `create_meet_subscription(meeting_name)`

```python
@frappe.whitelist()
def create_meet_subscription(meeting_name):
    # Get meeting
    meeting = frappe.get_doc("VidCon Meeting", meeting_name)
    
    # Validate space_id exists
    if not meeting.google_space_id:
        throw error
    
    # Create subscription for spaces/{space_id}
    response = create_subscription(
        space_resource=f"spaces/{meeting.google_space_id}",
        pubsub_topic=settings.pubsub_topic_name
    )
    
    # Store subscription ID
    meeting.db_set("meet_subscription_id", response.get("name"))
```

## Subscription Lifecycle

### Creation
- Created when user clicks button
- Subscription ID stored on meeting
- State: ACTIVE

### Active Period
- Google sends events to Pub/Sub topic
- Pub/Sub pushes to webhook
- Webhook processes events

### Expiration
- Subscriptions expire after some time (Google's policy)
- Need to renew or recreate
- Check status with "Check Subscription Status" button

### Deletion
- When meeting is deleted
- Or manually via API
- Subscription stops sending events

## Troubleshooting

### "Failed to create subscription"

**Check:**
1. VidCon Settings → Enable Meet Events ✅
2. VidCon Settings → Pub/Sub Topic Name is set
3. Meeting has `google_space_id` field populated
4. Google Calendar is authorized with Meet scopes
5. Error Log for actual error message

### "No subscription found"

**Cause:** Subscription was never created

**Fix:** Click "Create Meet Subscription" button

### Events not being received

**Check:**
1. Subscription exists (check `meet_subscription_id` field)
2. Subscription is ACTIVE (click "Check Subscription Status")
3. Pub/Sub push subscription configured correctly
4. Webhook endpoint accessible
5. Error Log for webhook calls

## Configuration Checklist

### VidCon Settings

- [ ] **Google Calendar** - Selected
- [ ] **Enable Meet Events** - Checked
- [ ] **Pub/Sub Topic Name** - `projects/YOUR_PROJECT/topics/meet-events`

### Google Cloud Console

- [ ] **Pub/Sub Topic** - Created (`meet-events`)
- [ ] **Push Subscription** - Created, pointing to webhook
- [ ] **Meet API** - Enabled
- [ ] **OAuth Scopes** - Include `meetings.space.readonly`

### Per Meeting

- [ ] **google_space_id** - Populated (automatic)
- [ ] **meet_subscription_id** - Populated (click button)

## Best Practices

### For Production
1. **Enable automatic subscriptions** - Modify `after_insert()` to auto-create
2. **Monitor subscription health** - Scheduled task to check status
3. **Auto-renew expiring subscriptions** - Before they expire
4. **Fallback to manual sync** - If subscription fails

### For Development/Testing
1. **Use manual sync** - Simpler, no Pub/Sub needed
2. **Create subscriptions selectively** - Only for meetings you're testing
3. **Check Error Logs frequently** - Understand the flow

### For Old Meetings
1. **Don't create subscriptions** - Meeting already ended
2. **Use "Sync from Google Meet"** - One-time sync
3. **Fetch transcript manually** - If needed

## Future Improvements

### Possible Enhancements
1. **Auto-create subscriptions** - On meeting creation
2. **Subscription health monitoring** - Scheduled task
3. **Auto-renewal** - Before expiration
4. **Bulk subscription creation** - For multiple meetings
5. **User-level subscriptions** - One subscription for all user's meetings
6. **Subscription pooling** - Reuse subscriptions for similar meetings

### Current Limitations
1. One subscription per meeting (can be quota-intensive)
2. Manual subscription creation required
3. No auto-renewal
4. No health monitoring
5. Subscriptions expire (need recreation)

---

**Created:** March 22, 2026  
**Related:** WEBHOOK_TROUBLESHOOTING.md, SYNC_FROM_GOOGLE.md, PUBSUB_SETUP.md
