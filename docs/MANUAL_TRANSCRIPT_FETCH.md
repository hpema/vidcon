# Manual Transcript Fetch Feature

**Date:** March 22, 2026  
**Purpose:** Allow users to manually fetch transcripts for old meetings that may have missed Pub/Sub events

## Overview

This feature adds a "Fetch Transcript" button to completed VidCon Meetings, allowing users to manually retrieve transcripts on-demand. This is useful for:

- **Old meetings** created before the event handler fixes
- **Meetings that missed Pub/Sub events** due to network issues or downtime
- **Re-fetching transcripts** if the original fetch failed
- **Testing** transcript retrieval without waiting for automatic processing

## How It Works

### Button Visibility

The "Fetch Transcript" button appears in the **Actions** dropdown when:
- Meeting has a `google_conference_id` (meeting was started)
- Meeting status is "Completed" or "In Progress"
- Meeting is not new (already saved)

### User Flow

1. User opens a completed VidCon Meeting
2. Clicks **Actions** → **Fetch Transcript**
3. Confirms the action in dialog
4. System fetches transcript from Google Meet API
5. Success message appears and form reloads with transcript

### What Happens Behind the Scenes

```python
@frappe.whitelist()
def fetch_transcript_manually(meeting_name):
    # 1. Validate permissions
    meeting.check_permission("write")
    
    # 2. Validate meeting status
    if meeting.status not in ["Completed", "In Progress"]:
        throw error
    
    # 3. Check for conference_id (required for Meet API)
    if not meeting.google_conference_id:
        throw error
    
    # 4. Call the same function used by Pub/Sub events
    fetch_transcript_for_conference(
        conference_id=meeting.google_conference_id,
        meeting_name=meeting.name
    )
    
    # 5. Return success/failure status
```

## Requirements

### Meeting Must Have:
- ✅ `google_conference_id` - Set when meeting starts
- ✅ Status: "Completed" or "In Progress"
- ✅ User must have write permission

### Meeting Does NOT Need:
- ❌ Pub/Sub subscription
- ❌ Event logs
- ❌ Specific time delay after completion

## Error Handling

### Common Errors and Solutions

**Error: "Meeting must be completed before fetching transcript"**
- **Cause:** Meeting status is "Scheduled" or "Cancelled"
- **Solution:** Meeting must be started and completed first

**Error: "No conference ID found"**
- **Cause:** Meeting was never started (no one joined)
- **Solution:** Cannot fetch transcript for meetings that never started

**Error: "No transcript found. Transcript may not be available yet"**
- **Cause:** Google hasn't processed the transcript yet
- **Solution:** Wait 10-15 minutes after meeting ends, then try again

**Error: "Failed to fetch transcript: [API error]"**
- **Cause:** Google Meet API error or permission issue
- **Solution:** Check Error Log for details, verify OAuth scopes

## Use Cases

### 1. Recovering Old Meetings

**Scenario:** You have meetings from before the event handler fixes were deployed.

**Steps:**
1. Open the old meeting
2. Manually update status to "Completed" if needed
3. If `google_conference_id` is missing:
   - You'll need to find it from Google Calendar or Meet API
   - Or the meeting cannot be recovered (never started)
4. Click "Fetch Transcript"

### 2. Missed Pub/Sub Events

**Scenario:** Server was down when meeting ended, Pub/Sub event was missed.

**Steps:**
1. Meeting will still be in "In Progress" status
2. Manually change status to "Completed"
3. Click "Fetch Transcript"
4. Transcript will be fetched and status updated

### 3. Re-fetching Failed Transcripts

**Scenario:** Transcript fetch failed due to temporary API issue.

**Steps:**
1. Open meeting with status "Completed" but no transcript
2. Click "Fetch Transcript"
3. System will re-attempt the fetch
4. If successful, status changes to "Transcript Retrieved"

## Code Files

### Backend
**File:** `/vidcon/vidcon/doctype/vidcon_meeting/vidcon_meeting.py`

```python
@frappe.whitelist()
def fetch_transcript_manually(meeting_name):
    """Manually fetch transcript for a completed meeting"""
    # Lines 310-361
```

### Frontend
**File:** `/vidcon/vidcon/doctype/vidcon_meeting/vidcon_meeting.js`

```javascript
// Add button to manually fetch transcript for completed meetings
if (frm.doc.google_conference_id && 
    ['Completed', 'In Progress'].includes(frm.doc.status) && 
    !frm.is_new()) {
    frm.add_custom_button(__('Fetch Transcript'), function() {
        // Lines 49-77
    }, __('Actions'));
}
```

## API Endpoint

**Method:** `vidcon.vidcon.doctype.vidcon_meeting.vidcon_meeting.fetch_transcript_manually`

**Parameters:**
- `meeting_name` (string, required) - Name of the VidCon Meeting

**Returns:**
```json
{
    "success": true,
    "message": "Transcript retrieved",
    "status": "Transcript Retrieved",
    "transcript_length": 1234
}
```

**Or on failure:**
```json
{
    "success": false,
    "message": "No transcript available yet"
}
```

## Permissions

Users need **write permission** on VidCon Meeting to fetch transcripts manually.

This prevents unauthorized users from triggering API calls.

## Limitations

### Cannot Fetch If:
- Meeting was never started (no `conference_id`)
- Meeting is still scheduled
- Transcript recording was disabled in Google Meet
- Meeting organizer doesn't have transcript permissions
- OAuth scopes are missing (`meetings.space.readonly`)

### Transcript Availability
- Transcripts typically available 10-15 minutes after meeting ends
- Very long meetings may take longer to process
- Transcripts only available if enabled during the meeting

## Testing

### Test Manual Fetch

1. **Create and complete a test meeting:**
   ```
   - Create VidCon Meeting
   - Start meeting (join with participant)
   - Enable transcript in Google Meet
   - End meeting
   - Wait 15 minutes
   ```

2. **Test the button:**
   ```
   - Open completed meeting
   - Verify "Fetch Transcript" button appears
   - Click button
   - Confirm dialog
   - Verify transcript is fetched
   - Check status changes to "Transcript Retrieved"
   ```

3. **Test error cases:**
   ```
   - Try on scheduled meeting → Should show error
   - Try on meeting without conference_id → Should show error
   - Try immediately after meeting → Should show "not available yet"
   ```

## Comparison: Automatic vs Manual

| Feature | Automatic (Pub/Sub) | Manual (Button) |
|---------|-------------------|-----------------|
| **Trigger** | Pub/Sub event | User clicks button |
| **Timing** | 10 min after meeting ends | On-demand |
| **Requirements** | Pub/Sub subscription | conference_id only |
| **Use Case** | Normal operation | Recovery, testing |
| **Reliability** | Depends on events | Direct API call |

## Future Enhancements

Potential improvements:
- Bulk fetch for multiple meetings
- Scheduled retry for failed fetches
- Notification when transcript becomes available
- Preview transcript before saving
- Export transcript to different formats

---

**Created by:** Cascade AI  
**Date:** March 22, 2026  
**Related:** MEETING_STATUS_FIX.md, REFACTORING_SUMMARY.md
