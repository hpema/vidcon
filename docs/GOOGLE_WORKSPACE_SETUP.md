# Google Workspace Events API Setup for VidCon

Complete guide for configuring Google Cloud Console and enabling Meet Events in VidCon.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Google Cloud Console Setup](#google-cloud-console-setup)
3. [OAuth Configuration](#oauth-configuration)
4. [Pub/Sub Configuration](#pubsub-configuration)
5. [VidCon Authorization](#vidcon-authorization)
6. [Enable Meet Events](#enable-meet-events)
7. [Troubleshooting](#troubleshooting)
8. [References](#references)

---

## Prerequisites

- Google Workspace account with admin access
- Google Cloud Project with billing enabled
- VidCon app installed and running
- Domain verified in Google Cloud Console

**Required APIs:**
- Google Calendar API
- Google Workspace Events API
- Google Meet API
- Cloud Pub/Sub API

---

## Google Cloud Console Setup

### 1. Enable Required APIs

**Reference:** [Enable APIs - Google Cloud Console](https://console.cloud.google.com/apis/library)

Navigate to **APIs & Services** → **Library** and enable:

1. **Google Calendar API**
   - Search: "Google Calendar API"
   - Click **Enable**

2. **Google Workspace Events API**
   - Search: "Google Workspace Events API"
   - Click **Enable**

3. **Google Meet API**
   - Search: "Google Meet API"
   - Click **Enable**

4. **Cloud Pub/Sub API**
   - Search: "Cloud Pub/Sub API"
   - Click **Enable**

### 2. Configure OAuth Consent Screen

**Reference:** [OAuth consent screen - Google Cloud](https://console.cloud.google.com/apis/credentials/consent)

Navigate to **APIs & Services** → **OAuth consent screen**

1. **User Type**: Select **Internal** (for Workspace) or **External**
2. Click **Create**
3. Fill in app information:
   - **App name**: VidCon
   - **User support email**: Your email
   - **Developer contact email**: Your email
4. Click **Save and Continue**

### 3. Add Required Scopes

**Reference:** [Choose scopes - Google Workspace Events API](https://developers.google.com/workspace/events/guides/auth)

On the **Scopes** page, click **Add or Remove Scopes** and add:

#### Sensitive Scopes:
- `https://www.googleapis.com/auth/calendar`
  - *See, edit, share, and permanently delete all the calendars you can access using Google Calendar*

- `https://www.googleapis.com/auth/calendar.events`
  - *View and edit events on all your calendars*

#### Restricted Scopes:
- `https://www.googleapis.com/auth/meetings.space.readonly`
  - *Read information about any of your Google Meet conferences*

- `https://www.googleapis.com/auth/drive.readonly`
  - *See and download all your Google Drive files*

- `https://www.googleapis.com/auth/drive.meet.readonly`
  - *See and download your Google Drive files that were created or edited by Google Meet*

Click **Update** → **Save and Continue**

### 4. Create OAuth 2.0 Client ID

**Reference:** [Create credentials - Google Cloud](https://console.cloud.google.com/apis/credentials)

Navigate to **APIs & Services** → **Credentials**

1. Click **Create Credentials** → **OAuth client ID**
2. **Application type**: **Web application**
3. **Name**: VidCon OAuth Client
4. **Authorized redirect URIs**: Add the following:
   ```
   https://YOUR_DOMAIN/api/method/vidcon.vidcon.doctype.vidcon_settings.google_auth.vidcon_callback
   ```
   Replace `YOUR_DOMAIN` with your actual domain (e.g., `www.pema.co.za`)

5. Click **Create**
6. **Save the Client ID and Client Secret** - you'll need these for ERPNext Google Settings

---

## OAuth Configuration

### 1. Configure Google Settings in ERPNext

**Reference:** [Google Settings - Frappe](https://frappeframework.com/docs/user/en/integrations/google-settings)

1. Search for **Google Settings** (Ctrl+K)
2. Check **Enable**
3. Enter **Client ID** (from step above)
4. Enter **Client Secret** (from step above)
5. Click **Save**

### 2. Create Google Calendar

1. Search for **Google Calendar** (Ctrl+K)
2. Click **New**
3. **Calendar Name**: VidCon Primary Calendar
4. **Google Calendar ID**: Your Google Calendar ID (e.g., `you@yourdomain.com`)
5. Click **Save**
6. **Do NOT click "Authorize API Access" yet** - we'll use VidCon's custom authorization

---

## Pub/Sub Configuration

**Reference:** [Create Pub/Sub topic - Google Workspace Events](https://developers.google.com/workspace/events/guides/create-subscription#create-pubsub-topic)

### 1. Create Pub/Sub Topic

Navigate to **Google Cloud Console** → **Pub/Sub** → **Topics**

**Direct link:** [Google Cloud Pub/Sub](https://console.cloud.google.com/cloudpubsub)

1. Click **Create Topic**
2. **Topic ID**: `meet-events`
3. **Leave "Add a default subscription" checked** ✓
4. Click **Create**
5. **Note the full topic name**: `projects/YOUR_PROJECT_ID/topics/meet-events`

### 2. Grant Publisher Permission

**Reference:** [Grant Pub/Sub permissions - Google Meet Events](https://developers.google.com/workspace/meet/api/guides/tutorial-events-python#configure_google_cloud_pubsub)

On the topic's page:

1. Go to **Permissions** tab
2. Click **Add Principal**
3. **New principals**: `meet-api-event-push@system.gserviceaccount.com`
4. **Role**: Select **Pub/Sub Publisher**
5. Click **Save**

**Important:** It can take a few minutes for permissions to propagate.

### 3. Configure Push Subscription (Optional)

If you want Pub/Sub to push events to your webhook:

1. Go to **Pub/Sub** → **Subscriptions**
2. Click on `meet-events-sub` (the default subscription)
3. Click **Edit**
4. **Delivery type**: Select **Push**
5. **Endpoint URL**: 
   ```
   https://YOUR_DOMAIN/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push
   ```
6. Click **Update**

---

## VidCon Authorization

### 1. Authorize with Extended Scopes

VidCon requires additional scopes beyond what Frappe's Google Calendar provides. Use VidCon's custom authorization:

1. Go to **VidCon Settings**
2. Select **Google Calendar**: VidCon Primary Calendar
3. Click **Actions** → **Authorize Google Calendar (VidCon)**
4. A new window will open with Google's OAuth consent screen
5. **Review the permissions** - you should see:
   - Calendar access
   - Meet conference access
   - Drive file access
6. Click **Allow**
7. You'll see a success page: "Authorization Successful"
8. Close the OAuth window

**What this does:**
- Requests OAuth tokens with all three required scopes:
  - `https://www.googleapis.com/auth/calendar`
  - `https://www.googleapis.com/auth/meetings.space.readonly`
  - `https://www.googleapis.com/auth/drive.readonly`
- Stores `authorization_code` and `refresh_token` in Google Calendar
- Bypasses Frappe's calendar-only scope limitation

### 2. Verify Authorization

Run in bench console:

```bash
bench --site YOUR_SITE console <<'EOF'
import frappe

# Check for refresh_token
has_token = frappe.db.exists("__Auth", {
    "doctype": "Google Calendar",
    "name": "VidCon Primary Calendar",
    "fieldname": "refresh_token"
})

print(f"Refresh token exists: {bool(has_token)}")
EOF
```

Should output: `Refresh token exists: True`

---

## Enable Meet Events

### 1. Configure VidCon Settings

1. Go to **VidCon Settings**
2. Fill in required fields:
   - **Google Calendar**: VidCon Primary Calendar
   - **Meeting Organizer Email**: Your email (e.g., `you@yourdomain.com`)
   - **Pub/Sub Topic Name**: `projects/YOUR_PROJECT_ID/topics/meet-events`
     - Replace `YOUR_PROJECT_ID` with your actual project ID
     - Example: `projects/rounds-288112/topics/meet-events`
3. **Don't check "Enable Meet Events" yet**
4. Click **Save**

### 2. Enable Meet Events

1. In **VidCon Settings**, check **Enable Meet Events**
2. Click **Save**
3. VidCon will create a Workspace Events subscription
4. You should see:
   - **Meet Subscription ID**: `subscriptions/SUBSCRIPTION_ID`
   - **Meet Subscription State**: `ACTIVE`

**Success message:**
```
Meet Events subscription created successfully!
```

### 3. Verify Subscription

Click **Actions** → **Check Subscription Status** to verify the subscription is active.

---

## Troubleshooting

### Error: "Google Calendar is not authorized"

**Cause:** Missing refresh_token in `__Auth` table

**Solution:**
1. Go to VidCon Settings
2. Click **Actions** → **Authorize Google Calendar (VidCon)**
3. Complete OAuth flow
4. Try enabling Meet Events again

### Error: "Request had insufficient authentication scopes"

**Cause:** Access token only has calendar scope, missing meet and drive scopes

**Solution:**
This was fixed in VidCon by creating a custom token refresh function. Ensure you're on the latest version:
```bash
cd apps/vidcon && git pull origin main
bench restart
```

**Technical details:**
- Frappe's `get_access_token()` includes `scope: calendar` when refreshing
- VidCon's `get_vidcon_access_token()` includes all three scopes
- The subscription manager uses the VidCon function

### Error: "You don't have permission to access Pub/Sub topic"

**Cause:** Either the topic doesn't exist or missing publisher permission

**Solution:**
1. Verify topic exists: `projects/YOUR_PROJECT_ID/topics/meet-events`
2. Check permissions on topic
3. Ensure `meet-api-event-push@system.gserviceaccount.com` has **Pub/Sub Publisher** role
4. Wait a few minutes for permissions to propagate

### Error: "include_resource is not supported"

**Cause:** Invalid `payloadOptions` in subscription body

**Solution:**
Fixed in latest version - `includeResource` is set to `False`. Update VidCon:
```bash
cd apps/vidcon && git pull origin main
bench restart
```

### No Events Appearing in VidCon Event Log

**Possible causes:**

1. **Subscription not active**
   - Check VidCon Settings → Meet Subscription State = "ACTIVE"
   - Click "Check Subscription Status" button

2. **Pub/Sub not configured for push**
   - Go to Pub/Sub → Subscriptions → `meet-events-sub`
   - Verify Delivery type is "Push"
   - Verify Endpoint URL is correct

3. **No meetings created yet**
   - Create a test VidCon Meeting
   - Join the meeting
   - Check VidCon Event Log after a few minutes

4. **Webhook endpoint not accessible**
   - Verify your domain is accessible from Google's servers
   - Check for firewall rules blocking Google IPs
   - Test webhook: `curl https://YOUR_DOMAIN/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`

---

## References

### Official Google Documentation

1. **Google Workspace Events API Overview**
   - https://developers.google.com/workspace/events

2. **Create a Google Workspace subscription**
   - https://developers.google.com/workspace/events/guides/create-subscription

3. **Choose Google Workspace Events API scopes**
   - https://developers.google.com/workspace/events/guides/auth

4. **Observe meeting events with Python (Tutorial)**
   - https://developers.google.com/workspace/meet/api/guides/tutorial-events-python

5. **Google Meet REST API Reference**
   - https://developers.google.com/meet/api/reference/rest

6. **Google Workspace Events API Reference**
   - https://developers.google.com/workspace/events/reference/rest

7. **Cloud Pub/Sub Documentation**
   - https://cloud.google.com/pubsub/docs

8. **OAuth 2.0 for Web Server Applications**
   - https://developers.google.com/identity/protocols/oauth2/web-server

### VidCon Implementation Files

- **OAuth Authorization**: `vidcon/vidcon/doctype/vidcon_settings/google_auth.py`
- **Subscription Manager**: `vidcon/vidcon/doctype/vidcon_meeting/subscription_manager.py`
- **Event Handler**: `vidcon/vidcon/doctype/vidcon_meeting/google_meet_events.py`
- **Settings Controller**: `vidcon/vidcon/doctype/vidcon_settings/vidcon_settings.py`

### Key Concepts

**Workspace Events API Subscription:**
- Monitors a target resource (user email)
- Receives specific event types (conference started/ended, participant joined/left, etc.)
- Sends events to a Pub/Sub topic
- Requires proper OAuth scopes

**OAuth Scopes Required:**
- `calendar` - Create and manage calendar events
- `meetings.space.readonly` - Read Meet conference information
- `drive.readonly` - Access transcripts and recordings

**Pub/Sub Flow:**
1. VidCon creates Workspace Events subscription
2. Google sends Meet events to Pub/Sub topic
3. Pub/Sub pushes events to VidCon webhook
4. VidCon logs events and processes them

**Service Accounts:**
- `meet-api-event-push@system.gserviceaccount.com` - Google's service account that publishes Meet events to your Pub/Sub topic

---

## Event Types Supported

VidCon subscribes to the following Meet event types:

1. **google.workspace.meet.conference.v2.started**
   - Triggered when a conference starts (first participant joins)

2. **google.workspace.meet.conference.v2.ended**
   - Triggered when a conference ends (last participant leaves)

3. **google.workspace.meet.participant.v2.joined**
   - Triggered when a participant joins the conference

4. **google.workspace.meet.participant.v2.left**
   - Triggered when a participant leaves the conference

5. **google.workspace.meet.transcript.v2.fileGenerated**
   - Triggered when a transcript is generated and saved to Drive

**Note:** Recording events (`google.workspace.meet.recording.v2.fileGenerated`) are available but not currently subscribed to by default.

---

## Security Considerations

1. **OAuth Client Secret**
   - Store securely in Google Settings
   - Never commit to version control
   - Rotate periodically

2. **Webhook Endpoint**
   - Must use HTTPS
   - Validate Pub/Sub messages
   - Implement rate limiting if needed

3. **Scopes**
   - Request minimum required scopes
   - Review scope permissions regularly
   - Users must consent to all scopes

4. **Service Account Permissions**
   - Only grant Pub/Sub Publisher role
   - Don't grant additional permissions
   - Monitor for unauthorized access

---

## Production Checklist

- [ ] All required APIs enabled in Google Cloud Console
- [ ] OAuth consent screen configured with all scopes
- [ ] OAuth client ID created with correct redirect URI
- [ ] Google Settings configured in ERPNext
- [ ] Google Calendar created
- [ ] Pub/Sub topic created: `projects/PROJECT_ID/topics/meet-events`
- [ ] Publisher permission granted to `meet-api-event-push@system.gserviceaccount.com`
- [ ] Pub/Sub subscription configured for push delivery (optional)
- [ ] VidCon authorization completed with extended scopes
- [ ] Refresh token verified in `__Auth` table
- [ ] VidCon Settings configured with correct topic name
- [ ] Meet Events enabled successfully
- [ ] Subscription ID and state verified
- [ ] Test meeting created and events received
- [ ] Events appearing in VidCon Event Log
- [ ] Webhook endpoint accessible from internet
- [ ] SSL certificate valid and not expired

---

**Last Updated:** February 8, 2026
**VidCon Version:** Latest (main branch)
