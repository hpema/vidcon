# Sync from Google Meet Feature

**Date:** March 22, 2026  
**Purpose:** Comprehensive sync to recover meeting state from Google Meet API when Pub/Sub events are missed

## Overview

The **"Sync from Google Meet"** button queries the Google Meet API directly to fetch the current state of a meeting and updates the local VidCon Meeting record accordingly. This is the **primary recovery tool** for meetings that missed Pub/Sub events.

## What It Does

### Fetches and Updates:
1. **Conference ID** - If not already set
2. **Meeting Status** - Updates to "In Progress" or "Completed" based on API data
3. **Start Time** - Actual time first participant joined
4. **End Time** - Actual time last participant left
5. **Transcript** - Downloads transcript if available

### Smart Updates:
- Only updates fields that are empty or need correction
- Doesn't overwrite existing data unnecessarily
- Shows exactly what was updated
- Handles partial data gracefully

## How It Works

### Technical Flow

```python
@frappe.whitelist()
def sync_from_google_meet(meeting_name):
    # 1. Get meeting and validate google_space_id exists
    
    # 2. Query Google Meet API by space_id
    conferences = meet_service.conferenceRecords().list(
        filter=f'space.name="spaces/{space_id}"'
    ).execute()
    
    # 3. Get most recent conference for this space
    conference = conferences[0]
    
    # 4. Update conference_id if missing
    if not meeting.google_conference_id:
        meeting.google_conference_id = conference_id
    
    # 5. Update start time if missing
    if start_time and not meeting.actual_start_time:
        meeting.actual_start_time = start_time
    
    # 6. Update end time and status
    if end_time:
        meeting.actual_end_time = end_time
        meeting.status = "Completed"
    elif start_time:
        meeting.status = "In Progress"
    
    # 7. Fetch transcript if meeting completed
    if end_time and not meeting.transcript:
        # Download transcript via Meet API
        # Update status to "Transcript Retrieved"
    
    # 8. Save and return list of updates
```

## Button Visibility

**Appears when:**
- Meeting has `google_space_id` (created successfully)
- Meeting is saved (not new)
- **Works for ANY status** (Scheduled, In Progress, Completed)

**Location:** Actions dropdown → "Sync from Google Meet"

## Use Cases

### 1. Missed Pub/Sub Events

**Scenario:** Server was down, Pub/Sub events never arrived

**Before Sync:**
- Status: "Scheduled"
- No conference_id
- No start/end times
- No transcript

**After Sync:**
- Status: "Completed" ✅
- conference_id: Set ✅
- Start time: Recorded ✅
- End time: Recorded ✅
- Transcript: Downloaded ✅

### 2. Old Meetings

**Scenario:** Meeting created before event handler fixes

**Steps:**
1. Open old meeting (still showing "Scheduled")
2. Click "Sync from Google Meet"
3. System fetches actual state from Google
4. Meeting updated with real data

### 3. Partial Updates

**Scenario:** Meeting started but didn't complete properly

**Before Sync:**
- Status: "In Progress"
- Start time: Set
- End time: Missing
- conference_id: Set

**After Sync:**
- Status: "Completed" ✅
- End time: Set ✅
- Transcript: Downloaded ✅

### 4. Status Verification

**Scenario:** Want to verify meeting actually completed

**Steps:**
1. Click "Sync from Google Meet"
2. If meeting ended: Status → "Completed"
3. If still in progress: Status → "In Progress"
4. If not started: "No conference found"

## What Gets Updated

### Always Checked:
- ✅ Conference ID
- ✅ Start time
- ✅ End time
- ✅ Meeting status
- ✅ Transcript (if meeting completed)

### Update Logic:

| Field | Update Condition |
|-------|-----------------|
| `google_conference_id` | If NULL |
| `actual_start_time` | If NULL and API has data |
| `actual_end_time` | If NULL and API has data |
| `status` | If "Scheduled" or "In Progress" and API shows ended |
| `transcript` | If NULL and meeting completed |
| `transcript_file_id` | If transcript fetched |
| `transcript_url` | If transcript fetched |

## Response Messages

### Success Messages:

**"Updated: Conference ID, Start time, End time, Status → Completed, Transcript"**
- Shows exactly what was updated

**"Meeting is already up to date"**
- All data already synced, nothing to update

### Error Messages:

**"No conference found for this meeting. Meeting may not have been started yet."**
- Meeting was created but never started (no one joined)

**"No Google Meet space ID found"**
- Meeting wasn't created properly via Google Calendar API

**"Failed to fetch from Google Meet API: [error]"**
- API error, check Error Log for details

## Requirements

### Meeting Must Have:
- ✅ `google_space_id` (set during meeting creation)

### Meeting Does NOT Need:
- ❌ `google_conference_id` (will be fetched)
- ❌ Pub/Sub subscription
- ❌ Event logs
- ❌ Specific status

### System Must Have:
- ✅ Google Meet API enabled
- ✅ OAuth scope: `meetings.space.readonly`
- ✅ Valid Google Calendar credentials

## Comparison: Sync vs Fetch Transcript

| Feature | Sync from Google Meet | Fetch Transcript |
|---------|---------------------|------------------|
| **Updates** | Status, times, conference_id, transcript | Transcript only |
| **Requirements** | google_space_id | google_conference_id |
| **Works for** | Any status | Completed meetings |
| **Use case** | Full recovery | Transcript retry |
| **API calls** | 2-3 calls | 1 call |

## Code Files

### Backend
**File:** `vidcon_meeting.py` (lines 310-476)

```python
@frappe.whitelist()
def sync_from_google_meet(meeting_name):
    """Sync meeting status, times, and transcript from Google Meet API"""
```

### Frontend
**File:** `vidcon_meeting.js` (lines 49-75)

```javascript
frm.add_custom_button(__('Sync from Google Meet'), function() {
    // Confirmation dialog with update details
    // API call with freeze screen
    // Success alert and form reload
}, __('Actions'));
```

## API Endpoint

**Method:** `vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.sync_from_google_meet`

**Parameters:**
- `meeting_name` (string, required)

**Returns:**
```json
{
    "success": true,
    "message": "Updated: Conference ID, Status → Completed, Transcript",
    "updates": ["Conference ID", "Status → Completed", "Transcript"],
    "status": "Transcript Retrieved"
}
```

## Error Handling

### Graceful Degradation:
- If transcript fetch fails, status still updates
- If conference not found, clear error message
- Logs all errors to Error Log
- Doesn't fail entire sync for partial failures

### Retry Strategy:
- Can be clicked multiple times
- Won't overwrite existing data
- Safe to run on already-synced meetings

## Testing

### Test Full Sync

1. **Create meeting but don't start it:**
   - Status should be "Scheduled"
   - No conference_id

2. **Start and complete meeting externally:**
   - Join via Google Meet link
   - Complete the meeting
   - Don't wait for Pub/Sub

3. **Sync from VidCon:**
   - Open meeting (still "Scheduled")
   - Click "Sync from Google Meet"
   - Verify all fields updated

### Test Partial Sync

1. **Meeting with conference_id but no end time:**
   - Manually set conference_id
   - Click sync
   - Should update end time and status only

### Test Already Synced

1. **Fully synced meeting:**
   - Click sync
   - Should show "Already up to date"

## Permissions

Users need **write permission** on VidCon Meeting to sync.

## Limitations

### Cannot Sync If:
- Meeting was never created in Google Calendar
- Meeting was deleted from Google
- OAuth credentials expired
- Google Meet API quota exceeded

### Data Availability:
- Conference data available for ~60 days after meeting
- Transcripts available if recording was enabled
- Participant details may be limited

## Best Practices

### When to Use:
- ✅ After server downtime
- ✅ For old meetings
- ✅ When status seems wrong
- ✅ Before exporting data

### When NOT to Use:
- ❌ For meetings that never started
- ❌ Repeatedly (won't change result)
- ❌ For meetings deleted from Google

## Troubleshooting

**Q: Sync says "No conference found" but meeting definitely happened**

A: Meeting may have been started via a different Meet link or the conference data expired (>60 days old)

**Q: Sync updated status but no transcript**

A: Transcript may not be available yet (wait 15 min) or recording wasn't enabled during meeting

**Q: Can I sync multiple meetings at once?**

A: Not currently, but could be added as bulk action in future

**Q: Will sync overwrite my manual changes?**

A: No, sync only updates NULL/empty fields and status progression

---

**Created by:** Cascade AI  
**Date:** March 22, 2026  
**Related:** MEETING_STATUS_FIX.md, MANUAL_TRANSCRIPT_FETCH.md
