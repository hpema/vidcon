# Google Workspace Events API Setup with Pub/Sub

This guide explains how to set up Google Workspace Events API with Cloud Pub/Sub to automatically monitor Google Meet conferences and retrieve transcripts.

## Overview

Google Workspace Events API uses a subscription model that sends events to a Google Cloud Pub/Sub topic, which then pushes notifications to your webhook endpoint. This allows VidCon to:

1. **Monitor meeting lifecycle** - Detect when meetings start and end
2. **Track participants** - Know when participants join/leave
3. **Auto-fetch transcripts** - Get notified when transcripts are ready
4. **Auto-fetch recordings** - Get notified when recordings are processed

## Key Events Available

| Event Type | Description | Use Case |
|------------|-------------|----------|
| `conference.started` | First participant joins | Update status to "In Progress" |
| `conference.ended` | Last participant leaves | Mark meeting as "Completed" |
| `participant.joined` | Someone joins the meeting | Track attendance |
| `participant.left` | Someone leaves the meeting | Track attendance |
| `transcript.fileGenerated` | Transcript is ready | Download and store transcript |
| `recording.fileGenerated` | Recording is ready | Download and store recording |

## Prerequisites

1. **Google Workspace account** with admin access
2. **HTTPS endpoint** - Your Frappe site must use HTTPS
3. **Public URL** - Site must be accessible from the internet
4. **Google Cloud Project** - Same project used for Calendar API

## Step 1: Enable Required APIs

Go to [Google Cloud Console](https://console.cloud.google.com/) and enable:

1. **Google Meet API**
   - Navigate to **APIs & Services** > **Library**
   - Search for "Google Meet API"
   - Click **Enable**

2. **Google Workspace Events API**
   - Search for "Google Workspace Events API"
   - Click **Enable**

3. **Google Drive API** (if not already enabled)
   - Search for "Google Drive API"
   - Click **Enable**

## Step 2: Create Pub/Sub Topic

1. In Google Cloud Console, go to **Pub/Sub** > **Topics**
2. Click **Create Topic**
3. Enter topic name: `meet-events`
4. Click **Create**
5. Note the full topic name: `projects/YOUR_PROJECT_ID/topics/meet-events`

## Step 3: Grant Pub/Sub Publisher Permission

The Google Meet API needs permission to publish to your topic:

1. In the topic details page, click **Permissions** tab
2. Click **Add Principal**
3. Enter principal: `meet-api-event-push@system.gserviceaccount.com`
4. Select role: **Pub/Sub Publisher**
5. Click **Save**

## Step 4: Create Push Subscription

This connects the Pub/Sub topic to your webhook endpoint:

1. In the topic details, click **Create Subscription**
2. Enter subscription ID: `meet-events-push`
3. Select delivery type: **Push**
4. Enter endpoint URL:
   ```
   https://your-domain.com/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push
   ```
5. Click **Create**

**Important**: Replace `your-domain.com` with your actual domain.

## Step 5: Update OAuth Scopes

Add the required scopes for Meet API and Drive API:

1. Go to **APIs & Services** > **OAuth consent screen**
2. Click **Edit App**
3. In **Scopes** section, click **Add or Remove Scopes**
4. Add these scopes:
   ```
   https://www.googleapis.com/auth/meetings.space.readonly
   https://www.googleapis.com/auth/drive.readonly
   ```
5. Save and continue

## Step 6: Re-authorize Google Calendar

Since we added new scopes, re-authorize:

1. In ERPNext, go to **Google Calendar** list
2. Open your calendar document
3. Click **Authorize API Access** button
4. Grant the new Meet and Drive permissions when prompted

## Step 7: Configure VidCon Settings

1. Search for **VidCon Settings** (Ctrl+K)
2. Configure the following:
   - **Google Calendar**: Select your calendar
   - **Enable Auto Transcript Fetch**: ✅ Checked
   - **Transcript Fetch Delay**: 10 minutes (default)
   - **Pub/Sub Topic Name**: `projects/YOUR_PROJECT_ID/topics/meet-events`
3. Save the settings

## Step 8: Create Meet Subscription

Run this in Frappe console to create the subscription:

```python
from vidcon.vidcon.doctype.vidcon_meeting.google_meet_events import create_meet_subscription

# Get the user email (meeting organizer)
user_email = "your-email@your-domain.com"

# Create subscription
response = create_meet_subscription(user_email)
print(response)
```

This will:
- Subscribe to Meet events for the specified user
- Register for conference.ended, transcript.ready, and recording.ready events
- Store subscription ID in VidCon Settings

## How It Works

### Event Flow

```
Google Meet Conference
    ↓
Event occurs (meeting ends, transcript ready, etc.)
    ↓
Google publishes event to Pub/Sub topic
    ↓
Pub/Sub pushes to your webhook endpoint
    ↓
VidCon processes the event
    ↓
Updates meeting status / Downloads transcript
```

### Pub/Sub Message Format

Google sends a POST request with this structure:

```json
{
  "message": {
    "data": "base64-encoded-event-data",
    "attributes": {
      "ce-type": "google.workspace.meet.conference.v2.ended",
      "ce-source": "//meet.googleapis.com/...",
      "ce-subject": "conferenceRecords/abc-defg-hij"
    },
    "messageId": "12345",
    "publishTime": "2026-02-08T10:00:00Z"
  }
}
```

### Event Data Example (conference.ended)

```json
{
  "conferenceRecord": {
    "name": "conferenceRecords/abc-defg-hij",
    "startTime": "2026-02-08T09:00:00Z",
    "endTime": "2026-02-08T10:00:00Z",
    "space": "spaces/xyz123"
  }
}
```

### Event Data Example (transcript.fileGenerated)

```json
{
  "transcript": {
    "name": "conferenceRecords/abc-defg-hij/transcripts/transcript123",
    "conferenceRecord": "conferenceRecords/abc-defg-hij",
    "state": "ENDED",
    "driveDestination": {
      "file": "files/1234567890abcdef",
      "exportUri": "https://drive.google.com/file/d/..."
    }
  }
}
```

## Verification

### Test the Webhook

1. Create a test VidCon Meeting
2. Join the Google Meet
3. Enable transcript recording (manually in Meet)
4. End the meeting
5. Check VidCon Meeting after 10-15 minutes:
   - Status should be "Completed"
   - Transcript should appear in Transcript section

### Check Pub/Sub Logs

In Google Cloud Console:

1. Go to **Pub/Sub** > **Subscriptions**
2. Click on `meet-events-push`
3. View **Metrics** tab to see message delivery

### Check VidCon Logs

```python
# In Frappe console
frappe.get_all("Error Log", 
    filters={"method": ["like", "%google_meet_events%"]},
    fields=["creation", "error", "method"],
    order_by="creation desc",
    limit=10
)
```

## Troubleshooting

### Webhook Not Receiving Messages

**Check endpoint accessibility:**
```bash
curl -X POST https://your-domain.com/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -d '{"message":{"data":""}}'
```

**Verify Pub/Sub subscription:**
- Go to Cloud Console > Pub/Sub > Subscriptions
- Check `meet-events-push` status
- Look for delivery errors

**Check HTTPS certificate:**
```bash
curl -I https://your-domain.com
```

### Transcripts Not Being Retrieved

**Verify Meet API is enabled:**
- Google Cloud Console > APIs & Services > Enabled APIs
- Confirm "Google Meet API" is listed

**Check OAuth scopes:**
```python
# In Frappe console
google_calendar = frappe.get_doc("Google Calendar", "your-calendar-name")
# Re-authorize if needed
```

**Manual transcript fetch:**
```python
from vidcon.vidcon.doctype.vidcon_meeting.google_meet_events import fetch_transcript_for_conference

fetch_transcript_for_conference("conference-id", "VIDCON-MTG-2026-00001")
```

### Subscription Not Created

**Check permissions:**
- Ensure OAuth user has Meet admin permissions
- Verify all required scopes are granted

**Check API quotas:**
- Go to Cloud Console > APIs & Services > Quotas
- Check Workspace Events API quota

**Manual subscription creation:**
```python
from vidcon.vidcon.doctype.vidcon_meeting.google_meet_events import create_meet_subscription

# Try with different user
create_meet_subscription("admin@your-domain.com")
```

## Security Considerations

### Pub/Sub Authentication

Pub/Sub push endpoints should verify the request:

1. **Check message signature** (optional but recommended)
2. **Validate message format**
3. **Rate limiting** to prevent abuse

### OAuth Token Security

- Tokens are encrypted in database
- Never log or expose tokens
- Use `get_password()` to access

### Webhook Endpoint

- Always use HTTPS
- Validate incoming data
- Return 200 status to acknowledge receipt

## API Quotas and Limits

### Google Workspace Events API

- **Subscriptions per user**: 100
- **Events per day**: Based on Meet usage
- **Subscription duration**: Indefinite (no expiration)

### Google Meet API

- **Queries per day**: 10,000
- **Queries per minute**: 600

### Pub/Sub

- **Messages per second**: 10,000
- **Message size**: 10 MB max

## Advanced Configuration

### Subscribe to Specific Meeting Space

Instead of subscribing to all meetings for a user:

```python
# Subscribe to specific space
subscription_body = {
    "targetResource": f"//meet.googleapis.com/spaces/{space_id}",
    "eventTypes": ["google.workspace.meet.conference.v2.ended"],
    # ...
}
```

### Filter Events

Add filtering in the webhook handler:

```python
def handle_conference_ended(event_data):
    # Only process meetings created by VidCon
    conference_id = event_data.get('conferenceRecord', {}).get('name', '').split('/')[-1]
    
    meetings = frappe.get_all(
        "VidCon Meeting",
        filters={"google_meet_link": ["like", f"%{conference_id}%"]},
        fields=["name"]
    )
    
    if not meetings:
        # Not a VidCon meeting, ignore
        return
    
    # Process the event...
```

### Custom Retry Logic

Modify retry behavior for transcript fetching:

```python
# In google_meet_events.py
def fetch_transcript_for_conference(conference_id, meeting_name, retry_count=0):
    max_retries = 3
    
    if retry_count >= max_retries:
        frappe.logger().error(f"Max retries reached for {meeting_name}")
        return
    
    # Attempt fetch...
    
    if not transcripts:
        # Retry with exponential backoff
        delay = (retry_count + 1) * 5  # 5, 10, 15 minutes
        frappe.enqueue(
            "vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.fetch_transcript_for_conference",
            conference_id=conference_id,
            meeting_name=meeting_name,
            retry_count=retry_count + 1,
            # Schedule for later
        )
```

## Production Checklist

- [ ] All required APIs enabled (Meet, Events, Drive)
- [ ] Pub/Sub topic created with correct permissions
- [ ] Push subscription created with HTTPS endpoint
- [ ] OAuth scopes updated and re-authorized
- [ ] VidCon Settings configured with Pub/Sub topic
- [ ] Meet subscription created for user/space
- [ ] Test meeting completed successfully
- [ ] Transcript retrieved automatically
- [ ] Pub/Sub metrics showing message delivery
- [ ] Error logs monitored
- [ ] HTTPS certificate valid

## Cost Considerations

### Google Cloud Pub/Sub Pricing

- **First 10 GB/month**: Free
- **Additional data**: $0.06 per GB
- **Typical VidCon usage**: < 1 GB/month (very low cost)

### API Usage

- All Google Workspace APIs used are **free** within quota limits
- No additional cost for Meet API or Events API

## Next Steps

1. **Test the complete flow** - Create meeting, end it, verify transcript
2. **Monitor for a week** - Ensure subscriptions stay active
3. **Add CRM integration** - Link meetings to Deals/Leads
4. **Build analytics** - Track meeting metrics and attendance

## Support Resources

- [Google Workspace Events API Docs](https://developers.google.com/workspace/events)
- [Google Meet API Docs](https://developers.google.com/meet/api)
- [Cloud Pub/Sub Docs](https://cloud.google.com/pubsub/docs)
- [VidCon GitHub Issues](https://github.com/hpema/vidcon/issues)
