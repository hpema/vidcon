# Google Calendar Push Notifications Setup

This guide explains how to set up Google Calendar push notifications (webhooks) to automatically monitor meeting completion and retrieve transcripts.

## Overview

Google Calendar API supports push notifications via webhooks. When enabled, Google will send HTTP POST requests to your webhook endpoint whenever calendar events change. This allows VidCon to:

1. **Monitor meeting status** - Detect when meetings end
2. **Auto-fetch transcripts** - Retrieve Google Meet transcripts from Google Drive after meetings complete
3. **Update meeting records** - Keep VidCon Meeting status synchronized with Google Calendar

## Prerequisites

1. **HTTPS endpoint** - Google requires webhooks to use HTTPS (not HTTP)
2. **Public URL** - Your Frappe site must be accessible from the internet
3. **Google Calendar API enabled** - Already done in main setup
4. **Google Drive API enabled** - Required for transcript retrieval

## Step 1: Enable Google Drive API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (same one used for Calendar API)
3. Navigate to **APIs & Services** > **Library**
4. Search for "Google Drive API"
5. Click **Enable**

## Step 2: Update OAuth Scopes

You need to add Drive API scope to access transcripts:

1. Go to **APIs & Services** > **OAuth consent screen**
2. Click **Edit App**
3. In **Scopes** section, click **Add or Remove Scopes**
4. Add the following scope:
   ```
   https://www.googleapis.com/auth/drive.readonly
   ```
5. Save and continue

## Step 3: Re-authorize Google Calendar

Since we added a new scope, you need to re-authorize:

1. In ERPNext, go to **Google Calendar** list
2. Open your calendar document
3. Click **Authorize API Access** button
4. Grant the new Drive permissions when prompted

## Step 4: Configure VidCon Settings

1. Search for **VidCon Settings** (Ctrl+K)
2. Enable the following options:
   - ✅ **Enable Auto Transcript Fetch**
   - ✅ **Enable Webhook**
3. Set **Transcript Fetch Delay** (default: 10 minutes)
   - Google Meet transcripts are typically available 10-15 minutes after meeting ends
4. The **Webhook URL** will be automatically populated:
   ```
   https://your-domain.com/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.handle_calendar_notification
   ```
5. Save the settings

## Step 5: Setup Calendar Watch

The calendar watch needs to be set up programmatically. Run this in Frappe console:

```python
from vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook import setup_calendar_watch

# Get your Google Calendar name from VidCon Settings
settings = frappe.get_single("VidCon Settings")
google_calendar_name = settings.google_calendar

# Setup the watch
response = setup_calendar_watch(google_calendar_name)
print(response)
```

This will:
- Register your webhook with Google Calendar
- Store the channel ID and resource ID in VidCon Settings
- Set expiration date (7 days from now)

## Step 6: Verify Setup

### Check Calendar Watch Status

In **VidCon Settings**, you should see:
- **Watch Channel ID** - Unique identifier for this watch
- **Watch Resource ID** - Google's resource identifier
- **Watch Expiration** - Date when watch expires (auto-renewed daily)

### Test the Webhook

1. Create a test VidCon Meeting
2. Join the Google Meet
3. End the meeting
4. Wait 10-15 minutes
5. Check the VidCon Meeting record:
   - Status should change to "Completed"
   - Transcript should appear in the Transcript section

### Check Logs

Monitor the webhook activity in **Error Log**:

```python
# In Frappe console
frappe.get_all("Error Log", 
    filters={"method": ["like", "%calendar_webhook%"]},
    fields=["creation", "error", "method"],
    order_by="creation desc",
    limit=10
)
```

## How It Works

### 1. Calendar Watch Setup
- VidCon registers a webhook URL with Google Calendar API
- Google sends notifications when events change
- Watch expires after 7 days (auto-renewed by scheduled task)

### 2. Event Notification Flow
```
Google Calendar Event Changes
    ↓
Google sends POST to webhook
    ↓
VidCon receives notification
    ↓
Fetch updated event details
    ↓
Update VidCon Meeting status
    ↓
If meeting ended → Trigger transcript fetch
```

### 3. Transcript Retrieval Flow
```
Meeting Ends
    ↓
Wait for transcript delay (10 min)
    ↓
Search Google Drive for transcript
    ↓
Download transcript content
    ↓
Store in VidCon Meeting
    ↓
Update status to "Transcript Retrieved"
```

## Scheduled Tasks

VidCon runs two scheduled tasks:

### 1. Calendar Watch Renewal (Daily)
- Checks if watch is expiring within 24 hours
- Automatically renews the watch
- Prevents notification interruption

### 2. Pending Transcript Check (Every 15 minutes)
- Finds completed meetings without transcripts
- Retries transcript fetch
- Handles cases where webhook missed the event

## Troubleshooting

### Webhook Not Receiving Notifications

**Check HTTPS:**
```bash
# Your site must use HTTPS
curl -I https://your-domain.com
```

**Verify webhook URL is accessible:**
```bash
curl -X POST https://your-domain.com/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.handle_calendar_notification
```

**Check watch status:**
```python
settings = frappe.get_single("VidCon Settings")
print(f"Channel ID: {settings.calendar_watch_channel_id}")
print(f"Expires: {settings.calendar_watch_expiration}")
```

### Transcripts Not Being Retrieved

**Check Drive API is enabled:**
- Go to Google Cloud Console
- Verify "Google Drive API" is enabled

**Check OAuth scopes:**
```python
google_calendar = frappe.get_doc("Google Calendar", "your-calendar-name")
# Re-authorize if needed
```

**Manual transcript fetch:**
```python
from vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook import fetch_meeting_transcript

fetch_meeting_transcript("VIDCON-MTG-2026-00001")
```

### Watch Expired

If the watch expires (after 7 days without renewal):

```python
from vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook import setup_calendar_watch

settings = frappe.get_single("VidCon Settings")
setup_calendar_watch(settings.google_calendar)
```

## Security Considerations

### Webhook Endpoint Security

The webhook endpoint is publicly accessible (required by Google). Consider:

1. **Validate requests** - Check X-Goog-Channel-ID header
2. **Rate limiting** - Prevent abuse
3. **Log monitoring** - Watch for suspicious activity

### OAuth Token Security

- Tokens are encrypted in the database
- Use `get_password()` to access tokens
- Never log or expose tokens

## Limitations

### Google Meet Transcript Availability

- **Manual transcripts only** - Gemini note-taking must be enabled manually during the meeting
- **Delay** - Transcripts typically available 10-15 minutes after meeting ends
- **Storage** - Transcripts stored in meeting organizer's Google Drive
- **Permissions** - OAuth user must have access to the Drive folder

### API Quotas

Google Calendar API quotas:
- **Push notifications**: 10,000 per day
- **Calendar events**: 1,000,000 queries per day

For high-volume usage, consider:
- Batch processing
- Caching event data
- Reducing notification frequency

## Advanced Configuration

### Custom Transcript Search

Modify the search query in `google_calendar_webhook.py`:

```python
# Default search
query = f"name contains '{meet_code}' and mimeType='text/plain'"

# Custom search (e.g., specific folder)
query = f"'{folder_id}' in parents and name contains '{meet_code}'"
```

### Webhook Retry Logic

Adjust retry behavior in `scheduled_tasks.py`:

```python
# Change retry interval
frappe.enqueue(
    "vidcon.vidcon.doctype.vidcon_meeting.google_calendar_webhook.fetch_meeting_transcript",
    queue="default",
    timeout=600,
    meeting_name=meeting_name,
    enqueue_after_commit=True,
    at_front=False,
    now=False
)
```

## Production Checklist

- [ ] HTTPS enabled on site
- [ ] Google Drive API enabled
- [ ] OAuth scopes updated and re-authorized
- [ ] Calendar watch setup and verified
- [ ] Webhook URL accessible from internet
- [ ] Scheduled tasks running (check scheduler)
- [ ] Test meeting completed successfully
- [ ] Transcript retrieved automatically
- [ ] Error logs monitored
- [ ] Watch renewal working (check after 6 days)

## Support

For issues or questions:
1. Check Error Logs in ERPNext
2. Review webhook logs in VidCon Settings
3. Test manually using console commands above
4. Verify Google Cloud Console settings
