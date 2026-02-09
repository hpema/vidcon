# VidCon - Google Meet Integration Research

## Date: Feb 7, 2026

## Objective
Build a video conferencing AI agent that:
1. Schedules Google Meet meetings
2. Monitors meeting completion
3. Retrieves transcripts from Google Meet
4. Stores transcripts in ERPNext for CRM records

---

## Existing Infrastructure We Can Leverage

### 1. **Frappe Google Calendar Integration** ✅
**Location:** `/home/frappe/frappe-bench/apps/frappe/frappe/integrations/doctype/google_calendar/`

**Key Features:**
- Full OAuth2 authentication with Google
- Bidirectional sync with Google Calendar
- **Google Meet link generation built-in** (`add_video_conferencing` field)
- Automatic Meet link retrieval (`hangoutLink` from API)
- Event creation/update/delete
- Sync tokens for efficient polling

**Key Methods:**
- `get_google_calendar_object()` - Returns authenticated Google Calendar API client
- `insert_event_to_google_calendar()` - Creates events with Meet links
- `update_event_in_google_calendar()` - Updates events
- `get_conference_data()` - Generates Meet conference data

**API Scopes Used:**
- `https://www.googleapis.com/auth/calendar` (Calendar API)

### 2. **Frappe Event DocType** ✅
**Location:** `/home/frappe/frappe-bench/apps/frappe/frappe/desk/doctype/event/`

**Key Fields:**
- `subject` - Meeting title
- `starts_on`, `ends_on` - Datetime fields
- `description` - Meeting description
- `add_video_conferencing` - Checkbox to enable Google Meet
- `google_meet_link` - Stores the Meet URL
- `google_calendar_event_id` - Links to Google Calendar event
- `event_participants` - Child table for attendees
- `status` - Open, Completed, Closed, Cancelled
- `reference_doctype`, `reference_docname` - Dynamic link to any doctype

**Integration Points:**
- Links to any doctype via Dynamic Link
- Already syncs with Google Calendar
- Already generates Google Meet links

### 3. **ERPNext CRM Module** ✅
**Location:** `/home/frappe/frappe-bench/apps/erpnext/erpnext/crm/`

**Key DocTypes:**
- **Appointment** - Has `calendar_event` link field to Event doctype
- **Lead** - CRM leads with contact info
- **Opportunity** - Sales opportunities

### 4. **Frappe CRM App** ✅
**Location:** `/home/frappe/frappe-bench/apps/crm/crm/fcrm/doctype/`

**Key DocTypes:**
- **CRM Deal** - Deal management with organization, contacts, products
- **CRM Lead** - Lead management with person/organization details
- **CRM Task** - Task management

**Integration Potential:**
- Both have communication tracking
- Both link to contacts/organizations
- Can link meetings to deals/leads

### 5. **Google Drive Integration** ✅
**Location:** `/home/frappe/frappe-bench/apps/frappe/frappe/integrations/doctype/google_drive/`

**Status:** Exists in Frappe
**Use Case:** Retrieve transcript files from Google Drive

---

## What Google Meet Provides

### Transcription Features (Google Workspace Enterprise)
1. **Automatic Transcription** - Google Meet can auto-transcribe meetings
2. **Transcript Storage** - Transcripts saved to Google Drive (meeting organizer's Drive)
3. **Transcript Format** - `.vtt` or `.srt` subtitle files + `.docx` document
4. **Transcript Location** - `My Drive > Meet Recordings` folder

### APIs We Need

#### 1. **Google Calendar API** (Already Integrated ✅)
- Create events with Meet links
- Monitor event status
- Get event details
- **Webhook Support:** Push notifications via Google Calendar API

#### 2. **Google Drive API** (Exists in Frappe ✅)
- Search for transcript files
- Download transcript content
- List files in specific folders

#### 3. **Google Meet API** (Limited)
- **Note:** Google Meet doesn't have a comprehensive public API
- Most functionality is through Calendar API
- Transcript retrieval is via Drive API

---

## Architecture Design

### DocTypes to Create

#### 1. **VidCon Settings** (Single)
Fields:
- `google_calendar` (Link to Google Calendar)
- `enable_auto_transcript_fetch` (Check)
- `transcript_fetch_delay` (Int - minutes after meeting ends)
- `default_meeting_duration` (Int - minutes)
- `enable_webhook` (Check)
- `webhook_url` (Data - for Google Calendar push notifications)

#### 2. **VidCon Meeting** (Master)
Fields:
- `title` (Data)
- `description` (Text Editor)
- `meeting_date` (Date)
- `start_time` (Time)
- `end_time` (Time)
- `status` (Select: Scheduled, In Progress, Completed, Transcript Retrieved, Failed)
- `event` (Link to Event - Frappe's Event doctype)
- `google_meet_link` (Data - read-only, fetched from Event)
- `google_calendar_event_id` (Data - read-only)
- `transcript` (Long Text)
- `transcript_file` (Attach)
- `actual_end_time` (Datetime)
- `transcript_retrieved_at` (Datetime)
- `reference_doctype` (Link - Lead, Deal, Opportunity, etc.)
- `reference_docname` (Dynamic Link)
- `attendees` (Table - child table)
- `meeting_notes` (Text Editor - manual notes)
- `ai_summary` (Long Text - future use)

#### 3. **VidCon Meeting Attendee** (Child Table)
Fields:
- `attendee_type` (Select: Internal, External)
- `reference_doctype` (Link - User, Contact, Lead Contact)
- `reference_docname` (Dynamic Link)
- `email` (Data)
- `full_name` (Data)
- `attended` (Check)

---

## Implementation Flow

### Phase 1: Meeting Scheduling
1. User creates VidCon Meeting from CRM Deal/Lead
2. System creates Frappe Event with `add_video_conferencing=1`
3. Event syncs to Google Calendar with Meet link
4. Meet link is fetched back and stored in VidCon Meeting
5. Attendees are added to Event participants

### Phase 2: Meeting Monitoring
**Option A: Polling (Simple)**
- Scheduled job runs every 5-10 minutes
- Checks VidCon Meetings with status "In Progress"
- Queries Google Calendar API for event status
- Detects if current time > end_time
- Updates status to "Completed"

**Option B: Webhook (Advanced)**
- Register webhook with Google Calendar API
- Receive push notifications when events change
- Update meeting status in real-time
- More efficient, less API calls

### Phase 3: Transcript Retrieval
1. Meeting status changes to "Completed"
2. Wait X minutes (configurable delay for Google to process)
3. Use Google Drive API to search for transcript:
   - Search in "Meet Recordings" folder
   - Filter by meeting date/time
   - Match by event ID or meeting title
4. Download transcript file
5. Parse and store in VidCon Meeting.transcript field
6. Attach original file to VidCon Meeting
7. Update status to "Transcript Retrieved"

### Phase 4: CRM Integration
1. Link VidCon Meeting to CRM Deal/Lead via reference fields
2. Show meetings in CRM Deal/Lead timeline
3. Display transcript in CRM context
4. Future: AI-powered action items, summaries, sentiment analysis

---

## Technical Requirements

### Google Workspace Setup
- ✅ Google Workspace account (User confirmed)
- ✅ Enable Google Calendar API
- ✅ Enable Google Drive API
- ✅ Configure OAuth consent screen
- ✅ Create OAuth credentials (Client ID & Secret)
- ✅ Enable Google Meet transcription (Workspace Enterprise feature)

### Frappe/ERPNext Setup
1. Configure Google Settings doctype (OAuth credentials)
2. Create Google Calendar doctype record
3. Authorize Google Calendar access
4. Install VidCon app
5. Run migrations to create doctypes
6. Configure VidCon Settings

### Python Dependencies
- `google-api-python-client` (Already in Frappe)
- `google-auth` (Already in Frappe)
- `google-auth-oauthlib` (Already in Frappe)

---

## API Endpoints to Build

### 1. Meeting Management
- `vidcon.api.create_meeting(title, description, start, end, attendees, reference_doctype, reference_docname)`
- `vidcon.api.update_meeting(meeting_name, **kwargs)`
- `vidcon.api.cancel_meeting(meeting_name)`
- `vidcon.api.get_meeting_status(meeting_name)`

### 2. Transcript Management
- `vidcon.api.fetch_transcript(meeting_name)`
- `vidcon.api.search_transcript_in_drive(event_id, meeting_date)`
- `vidcon.api.parse_transcript(file_content)`

### 3. Webhook Handler
- `vidcon.api.webhook.google_calendar_webhook()` (Whitelisted endpoint)

### 4. Scheduled Jobs
- `vidcon.tasks.monitor_meetings()` - Check meeting status
- `vidcon.tasks.fetch_pending_transcripts()` - Retrieve transcripts

---

## Advantages of This Approach

1. **Leverage Existing Infrastructure** - 80% of Google integration already done
2. **Native Google Meet** - No bot participants, clean UX
3. **Official APIs** - Reliable, supported by Google
4. **CRM Integration** - Seamless linking to deals/leads
5. **Scalable** - Works for internal and external meetings
6. **Future-Proof** - Easy to add AI features later

---

## Limitations & Considerations

1. **Google Workspace Enterprise Required** - For automatic transcription
2. **Transcript Delay** - Google takes 5-30 minutes to process transcripts
3. **Transcript Availability** - Only if organizer has transcription enabled
4. **No Real-Time Transcription** - Post-meeting only
5. **Drive API Quota** - Need to monitor API usage limits

---

## Next Steps

1. ✅ Research complete
2. Create VidCon Settings DocType
3. Create VidCon Meeting DocType
4. Create VidCon Meeting Attendee DocType
5. Build meeting creation API
6. Build monitoring scheduled job
7. Build transcript retrieval API
8. Test end-to-end flow
9. Build UI integration with CRM
10. Documentation and deployment
