# VidCon Setup Guide - Google Workspace Integration

## Prerequisites

Before starting, ensure you have:
- ✅ Google Workspace account (Enterprise edition recommended for transcription)
- ✅ Admin access to Google Workspace
- ✅ Admin access to your Frappe/ERPNext instance
- ✅ Access to Google Cloud Console

---

## Part 1: Google Cloud Console Setup

### Step 1: Create or Select a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google Workspace admin account
3. Click on the project dropdown at the top of the page
4. Click **"New Project"** or select an existing project
5. If creating new:
   - **Project Name:** `VidCon ERPNext Integration` (or your preferred name)
   - **Organization:** Select your organization
   - Click **"Create"**
6. Wait for the project to be created (takes ~30 seconds)

### Step 2: Enable Required APIs

1. In the Google Cloud Console, ensure your project is selected
2. Navigate to **"APIs & Services" > "Library"** (or use the search bar)
3. Enable the following APIs (search for each and click "Enable"):

   **a) Google Calendar API**
   - Search for "Google Calendar API"
   - Click on it
   - Click **"Enable"**
   - Wait for confirmation

   **b) Google Drive API**
   - Search for "Google Drive API"
   - Click on it
   - Click **"Enable"**
   - Wait for confirmation

   **c) Google Meet API** (Optional - limited functionality)
   - Search for "Google Meet API"
   - Click on it
   - Click **"Enable"** if available
   - Note: This API has limited public endpoints

### Step 3: Configure OAuth Consent Screen

1. Navigate to **"APIs & Services" > "OAuth consent screen"**
2. Select **User Type:**
   - Choose **"Internal"** if only for your organization
   - Choose **"External"** if you need external users (requires verification)
3. Click **"Create"**

4. **Fill in App Information:**
   - **App name:** `VidCon Meeting Manager`
   - **User support email:** Your email address
   - **App logo:** (Optional) Upload your company logo
   - **Application home page:** Your ERPNext URL (e.g., `https://erp.yourcompany.com`)
   - **Application privacy policy link:** Your privacy policy URL
   - **Application terms of service link:** Your terms of service URL
   - **Authorized domains:** Add your ERPNext domain (e.g., `yourcompany.com`)
   - **Developer contact information:** Your email address

5. Click **"Save and Continue"**

6. **Add Scopes:**
   - Click **"Add or Remove Scopes"**
   - Search and select the following scopes:
     - `https://www.googleapis.com/auth/calendar` - See, edit, share, and permanently delete all calendars
     - `https://www.googleapis.com/auth/calendar.events` - View and edit events on all calendars
     - `https://www.googleapis.com/auth/drive.readonly` - View files in Google Drive
     - `https://www.googleapis.com/auth/drive.metadata.readonly` - View metadata for files in Google Drive
   - Click **"Update"**
   - Click **"Save and Continue"**

7. **Test Users** (if External):
   - Add email addresses of users who can test the app
   - Click **"Save and Continue"**

8. **Review Summary:**
   - Review all information
   - Click **"Back to Dashboard"**

### Step 4: Create OAuth 2.0 Credentials

1. Navigate to **"APIs & Services" > "Credentials"**
2. Click **"+ Create Credentials"** at the top
3. Select **"OAuth client ID"**

4. **Configure OAuth Client:**
   - **Application type:** Select **"Web application"**
   - **Name:** `VidCon ERPNext OAuth Client`
   
5. **Add Authorized Redirect URIs:**
   - Click **"+ Add URI"** under "Authorized redirect URIs"
   - Add your ERPNext callback URL:
     ```
     https://your-erpnext-domain.com/api/method/frappe.integrations.google_oauth.callback
     ```
   - Replace `your-erpnext-domain.com` with your actual domain
   - Examples:
     - `https://erp.yourcompany.com/api/method/frappe.integrations.google_oauth.callback`
     - `http://localhost:8000/api/method/frappe.integrations.google_oauth.callback` (for local development)
   
6. Click **"Create"**

7. **Save Your Credentials:**
   - A popup will appear with your credentials
   - **Copy and save these immediately:**
     - **Client ID:** `xxxxx.apps.googleusercontent.com`
     - **Client Secret:** `xxxxxxxxxxxxxxxx`
   - Click **"Download JSON"** to save a backup
   - Click **"OK"**

   ⚠️ **IMPORTANT:** Keep these credentials secure! Treat them like passwords.

---

## Part 2: Google Workspace Admin Console Setup

### Step 5: Enable Google Meet Recording & Transcription

1. Go to [Google Admin Console](https://admin.google.com/)
2. Sign in with your Workspace admin account
3. Navigate to **"Apps" > "Google Workspace" > "Google Meet"**
4. Click on **"Meet video settings"**

5. **Enable Recording:**
   - Find **"Recording"** section
   - Check **"Let people record their meetings"**
   - Select who can record (recommended: **"Users in my organization"**)

6. **Enable Transcription:**
   - Find **"Transcription"** section
   - Check **"Let people use transcription"**
   - ⚠️ **Note:** Transcription requires Google Workspace Enterprise edition
   - If you don't see this option, check your Workspace edition

7. Click **"Save"**

### Step 6: Configure Meet Settings for Your Organization

1. In the same **"Meet video settings"** page:
   - **Host management:** Enable host controls
   - **Meeting attendance:** Enable attendance tracking (optional)
   - **Live streaming:** Configure as needed

2. Click **"Save"**

---

## Part 3: Frappe/ERPNext Configuration

### Step 7: Configure Google Settings in Frappe

1. Log in to your ERPNext instance as **Administrator**
2. Go to **"Google Settings"** doctype:
   - Use the search bar (Ctrl+K or Cmd+K)
   - Type: `Google Settings`
   - Press Enter

3. **Fill in OAuth Credentials:**
   - **Client ID:** Paste the Client ID from Step 4
   - **Client Secret:** Paste the Client Secret from Step 4
   - Click **"Save"**

### Step 8: Create Google Calendar Account

1. Go to **"Google Calendar"** doctype:
   - Use the search bar
   - Type: `Google Calendar`
   - Click **"New"**

2. **Fill in Details:**
   - **User:** Select your user (e.g., `Administrator` or your email)
   - **Calendar Name:** `VidCon Primary Calendar` (or your preferred name)
   - **Enable:** Check this box
   - **Pull from Google Calendar:** Check this box
   - **Push to Google Calendar:** Check this box
   - **Sync as Public:** Uncheck (keep meetings private)

3. Click **"Save"**

### Step 9: Authorize Google Calendar Access

1. After saving, you'll see a button: **"Allow Google Calendar Access"**
2. Click this button
3. You'll be redirected to Google's OAuth consent screen
4. **Sign in** with your Google Workspace account
5. **Review permissions:**
   - The app will request access to your Calendar and Drive
   - Click **"Allow"** or **"Continue"**
6. You'll be redirected back to ERPNext
7. The Google Calendar document should now show:
   - **Authorization Code:** (encrypted)
   - **Refresh Token:** (encrypted)
   - **Google Calendar ID:** (auto-generated)

### Step 10: Test Google Calendar Integration

1. Go to **"Event"** doctype:
   - Use the search bar
   - Type: `Event`
   - Click **"New"**

2. **Create a Test Event:**
   - **Subject:** `Test Google Meet Integration`
   - **Starts On:** Select a date/time in the future
   - **Ends On:** Select end time (e.g., 30 minutes later)
   - **Add Video Conferencing:** Check this box ✅
   - **Sync with Google Calendar:** Check this box ✅
   - **Google Calendar:** Select your calendar from Step 8

3. Click **"Save"**

4. **Verify:**
   - The event should sync to Google Calendar
   - A **Google Meet Link** should appear in the Event form
   - Check your Google Calendar - the event should be there with a Meet link
   - Click the Meet link to verify it works

5. If successful, you'll see:
   - `google_meet_link` field populated (e.g., `https://meet.google.com/xxx-yyyy-zzz`)
   - `google_calendar_event_id` field populated

---

## Part 4: Install VidCon App

### Step 11: Install the VidCon App

1. Open terminal on your Frappe server
2. Navigate to your bench directory:
   ```bash
   cd /home/frappe/frappe-bench
   ```

3. Install the VidCon app (if not already installed):
   ```bash
   bench get-app /home/frappe/frappe-bench/apps/vidcon
   ```

4. Install the app to your site:
   ```bash
   bench --site [your-site-name] install-app vidcon
   ```
   Replace `[your-site-name]` with your actual site name (e.g., `site1.local`)

5. Run migrations:
   ```bash
   bench --site [your-site-name] migrate
   ```

6. Restart bench:
   ```bash
   bench restart
   ```

### Step 12: Verify VidCon Installation

1. Log back into ERPNext
2. Search for **"VidCon Settings"** in the search bar
3. If you see the doctype, installation was successful
4. If not, check the error logs:
   ```bash
   bench --site [your-site-name] console
   ```

---

## Part 5: VidCon Configuration

### Step 13: Configure VidCon Settings

1. Go to **"VidCon Settings"**
2. **Fill in Configuration:**
   - **Google Calendar:** Select the calendar you created in Step 8
   - **Enable Auto Transcript Fetch:** Check this box
   - **Transcript Fetch Delay:** `10` (minutes after meeting ends)
   - **Default Meeting Duration:** `30` (minutes)
   - **Enable Webhook:** Uncheck for now (we'll implement polling first)

3. Click **"Save"**

---

## Part 6: Testing & Verification

### Step 14: Create a Test Meeting

1. Go to **"VidCon Meeting"** doctype
2. Click **"New"**
3. **Fill in Details:**
   - **Title:** `Test Meeting - VidCon Integration`
   - **Description:** `Testing the VidCon Google Meet integration`
   - **Meeting Date:** Today's date
   - **Start Time:** Current time + 5 minutes
   - **End Time:** Current time + 10 minutes
   - **Reference Doctype:** Select `CRM Deal` or `CRM Lead` (optional)
   - **Reference Docname:** Select a deal/lead (optional)

4. **Add Attendees:**
   - Add yourself and another test user
   - Include email addresses

5. Click **"Save"**

6. **Verify:**
   - Status should be **"Scheduled"**
   - Event link should be populated
   - Google Meet Link should appear
   - Check Google Calendar - event should be there

### Step 15: Test Meeting Flow

1. **Join the meeting:**
   - Click the Google Meet link
   - Join the meeting
   - **Enable transcription** in the meeting:
     - Click the three dots (⋮) in the meeting
     - Select **"Record meeting"** or **"Turn on captions"**
     - Enable **"Save transcript"**

2. **Conduct a short test:**
   - Speak for 1-2 minutes
   - Say some test phrases
   - End the meeting

3. **Wait for processing:**
   - Google takes 5-30 minutes to process transcripts
   - The transcript will be saved to your Google Drive
   - Location: `My Drive > Meet Recordings`

4. **Check VidCon Meeting:**
   - After the configured delay (10 minutes)
   - The scheduled job should fetch the transcript
   - Status should change to **"Transcript Retrieved"**
   - Transcript field should be populated

---

## Troubleshooting

### Issue: "OAuth Error" or "Authorization Failed"

**Solution:**
1. Verify redirect URI in Google Cloud Console matches exactly
2. Check that Client ID and Client Secret are correct in Google Settings
3. Try re-authorizing the Google Calendar

### Issue: "No Meet Link Generated"

**Solution:**
1. Ensure **"Add Video Conferencing"** is checked in Event
2. Verify Google Calendar is properly authorized
3. Check that Calendar API is enabled in Google Cloud Console
4. Try creating a new event manually in Google Calendar to test

### Issue: "Transcript Not Retrieved"

**Solution:**
1. Verify transcription was enabled during the meeting
2. Check Google Drive for transcript file in `Meet Recordings` folder
3. Ensure Drive API is enabled in Google Cloud Console
4. Check VidCon Settings - transcript fetch delay might be too short
5. Check error logs: `bench --site [site-name] logs`

### Issue: "Permission Denied" Errors

**Solution:**
1. Verify OAuth scopes include Calendar and Drive read access
2. Re-authorize Google Calendar access
3. Check Google Workspace admin settings for API restrictions

### Issue: Scheduled Job Not Running

**Solution:**
1. Check if scheduler is enabled:
   ```bash
   bench --site [site-name] enable-scheduler
   ```
2. Restart bench:
   ```bash
   bench restart
   ```
3. Check scheduler logs:
   ```bash
   bench --site [site-name] doctor
   ```

---

## Important Notes

### Transcript Availability
- ⚠️ **Transcription requires Google Workspace Enterprise edition**
- Transcripts are only generated if enabled during the meeting
- Processing time: 5-30 minutes after meeting ends
- Transcripts are saved to the meeting organizer's Google Drive

### API Quotas
- Google Calendar API: 1,000,000 queries per day (default)
- Google Drive API: 1,000,000,000 queries per day (default)
- Monitor usage in Google Cloud Console: **"APIs & Services" > "Dashboard"**

### Security Best Practices
- Keep OAuth credentials secure
- Use HTTPS for production environments
- Regularly rotate OAuth tokens
- Limit API access to necessary scopes only
- Review Google Cloud audit logs periodically

### Data Privacy
- Meeting transcripts contain sensitive information
- Ensure compliance with data protection regulations (GDPR, etc.)
- Configure appropriate user permissions in ERPNext
- Consider data retention policies

---

## Next Steps

Once setup is complete:

1. ✅ **Verify all tests pass**
2. ✅ **Configure user permissions** for VidCon doctypes
3. ✅ **Train users** on creating meetings from CRM
4. ✅ **Monitor API usage** in Google Cloud Console
5. ✅ **Set up backup procedures** for transcripts
6. 🚀 **Start using VidCon** for your meetings!

---

## Support & Resources

- **Frappe Documentation:** https://frappeframework.com/docs
- **Google Calendar API:** https://developers.google.com/calendar
- **Google Drive API:** https://developers.google.com/drive
- **Google Workspace Admin Help:** https://support.google.com/a

---

## Checklist

Use this checklist to track your progress:

### Google Cloud Console
- [ ] Created/selected Google Cloud project
- [ ] Enabled Google Calendar API
- [ ] Enabled Google Drive API
- [ ] Configured OAuth consent screen
- [ ] Created OAuth 2.0 credentials
- [ ] Saved Client ID and Client Secret

### Google Workspace Admin
- [ ] Enabled Google Meet recording
- [ ] Enabled Google Meet transcription
- [ ] Configured Meet settings

### Frappe/ERPNext
- [ ] Configured Google Settings with OAuth credentials
- [ ] Created Google Calendar account
- [ ] Authorized Google Calendar access
- [ ] Tested Event creation with Meet link
- [ ] Installed VidCon app
- [ ] Configured VidCon Settings

### Testing
- [ ] Created test VidCon Meeting
- [ ] Verified Meet link generation
- [ ] Conducted test meeting with transcription
- [ ] Verified transcript retrieval
- [ ] Tested CRM integration

---

**Setup Complete!** 🎉

You're now ready to start building the VidCon integration. Return to the development team when ready to proceed with implementation.
