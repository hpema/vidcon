# VidCon Architecture - App-Managed Google Meet Events

## Design Principles

1. **Zero Manual Configuration** - App manages all Google API subscriptions automatically
2. **UI-Driven Setup** - All configuration through VidCon Settings UI
3. **Automatic Event Handling** - No scheduled tasks for polling, pure event-driven
4. **Real-time Updates** - Meeting status and participants updated as events occur

## User Requirements

1. User creates meeting → Meeting syncs to Google Calendar with Meet link
2. Attendees join → VidCon tracks participants automatically
3. Meeting ends → VidCon updates status to "Completed"
4. Transcript generated → VidCon downloads and stores automatically
5. All transcripts stored as read-only

## Architecture Components

### 1. VidCon Settings (Single DocType)

**Purpose**: Central configuration for Google Meet integration

**Fields**:
```
Google Integration:
- google_calendar (Link to Google Calendar)
- meeting_organizer_email (Data) - Email of user who organizes meetings

Pub/Sub Configuration:
- pubsub_topic_name (Data) - projects/PROJECT_ID/topics/meet-events
- pubsub_subscription_endpoint (Data, Read-only) - Auto-populated webhook URL

Meet Events Subscription:
- enable_meet_events (Check) - Master switch for event monitoring
- meet_subscription_id (Data, Read-only) - Subscription ID from Google
- meet_subscription_state (Select, Read-only) - ACTIVE/SUSPENDED/DELETED
- subscription_target_user (Data, Read-only) - User being monitored

Transcript Settings:
- enable_auto_transcript_fetch (Check) - Auto-download transcripts
- transcript_fetch_delay (Int) - Delay in minutes (default: 0 for immediate)
```

**Auto-Setup Logic**:
```python
def on_save():
    # Auto-populate webhook endpoint
    self.pubsub_subscription_endpoint = get_url() + "/api/method/..."
    
    # If enable_meet_events is checked and no subscription exists
    if self.enable_meet_events and not self.meet_subscription_id:
        create_meet_subscription()
    
    # If enable_meet_events is unchecked and subscription exists
    elif not self.enable_meet_events and self.meet_subscription_id:
        delete_meet_subscription()
```

### 2. VidCon Meeting (Master DocType)

**Purpose**: Track individual meetings and their lifecycle

**Key Fields**:
```
Meeting Details:
- title, description, meeting_date, start_time, end_time

Google Integration:
- event (Link to Event) - Frappe Event document
- google_meet_link (Data) - Meet URL
- google_space_id (Data) - Space ID from Meet link
- google_conference_id (Data) - Conference record ID

Status Tracking:
- status (Select) - Scheduled/In Progress/Completed/Transcript Retrieved
- actual_start_time (Datetime) - When first participant joined
- actual_end_time (Datetime) - When last participant left

Participants:
- attendees (Table) - VidCon Meeting Attendee child table

Transcript:
- transcript (Long Text, Read-only)
- transcript_file_id (Data, Hidden)
- transcript_url (Data, Read-only)
- transcript_retrieved_at (Datetime, Read-only)
```

**Auto-Update Logic**:
```python
def after_insert():
    # Extract space ID from Meet link
    if self.google_meet_link:
        self.google_space_id = extract_space_id(self.google_meet_link)
        self.save()
```

### 3. VidCon Meeting Attendee (Child Table)

**Purpose**: Track meeting participants

**Fields**:
```
- email (Data, Required)
- full_name (Data, Required)
- attendee_type (Select) - Internal/External
- reference_doctype (Link) - Contact/Lead/Deal
- reference_docname (Dynamic Link)
- joined_at (Datetime) - When they joined
- left_at (Datetime) - When they left
- attended (Check) - Whether they actually joined
```

**Auto-Creation**:
- Created automatically when `participant.v2.joined` event received
- Updated when `participant.v2.left` event received

### 4. Google Meet Events Handler

**File**: `google_meet_events.py`

**Webhook Endpoint**: `/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push`

**Event Handlers**:

```python
def handle_pubsub_push():
    """Main webhook endpoint - receives all Pub/Sub messages"""
    # Decode Pub/Sub message
    # Route to specific handler based on event type
    
def handle_conference_started(event_data):
    """conference.v2.started"""
    # Find VidCon Meeting by space_id
    # Update status to "In Progress"
    # Set actual_start_time
    
def handle_conference_ended(event_data):
    """conference.v2.ended"""
    # Find VidCon Meeting by conference_id
    # Update status to "Completed"
    # Set actual_end_time
    
def handle_participant_joined(event_data):
    """participant.v2.joined"""
    # Find VidCon Meeting by conference_id
    # Create/update VidCon Meeting Attendee
    # Set joined_at timestamp
    # Mark attended = True
    
def handle_participant_left(event_data):
    """participant.v2.left"""
    # Find VidCon Meeting Attendee
    # Set left_at timestamp
    
def handle_transcript_file_generated(event_data):
    """transcript.v2.fileGenerated"""
    # Find VidCon Meeting by conference_id
    # Download transcript from Drive
    # Store in transcript field
    # Update status to "Transcript Retrieved"
    # Set transcript_retrieved_at
```

### 5. Subscription Management

**File**: `subscription_manager.py`

**Functions**:

```python
def create_meet_subscription(user_email):
    """
    Create Google Workspace Events subscription for a user.
    Called automatically when VidCon Settings.enable_meet_events is checked.
    
    Target Resource: //cloudidentity.googleapis.com/users/{user_email}
    Event Types:
        - google.workspace.meet.conference.v2.started
        - google.workspace.meet.conference.v2.ended
        - google.workspace.meet.participant.v2.joined
        - google.workspace.meet.participant.v2.left
        - google.workspace.meet.transcript.v2.fileGenerated
    
    Returns: subscription_id
    """
    
def delete_meet_subscription(subscription_id):
    """
    Delete Google Workspace Events subscription.
    Called when VidCon Settings.enable_meet_events is unchecked.
    """
    
def get_subscription_status(subscription_id):
    """
    Check subscription status.
    Returns: ACTIVE, SUSPENDED, or DELETED
    """
```

## Event Flow Diagrams

### Meeting Creation Flow
```
User creates VidCon Meeting
    ↓
VidCon creates Google Calendar Event
    ↓
Google Calendar creates Meet space
    ↓
Meet link returned to VidCon
    ↓
VidCon extracts space_id and stores in meeting
    ↓
Meeting ready (status: Scheduled)
```

### Meeting Lifecycle Flow
```
First participant joins
    ↓
Google publishes: conference.v2.started
    ↓
Pub/Sub → VidCon webhook
    ↓
VidCon updates status: "In Progress"
    ↓
VidCon sets actual_start_time

Participants join/leave
    ↓
Google publishes: participant.v2.joined/left
    ↓
Pub/Sub → VidCon webhook
    ↓
VidCon creates/updates attendee records

Last participant leaves
    ↓
Google publishes: conference.v2.ended
    ↓
Pub/Sub → VidCon webhook
    ↓
VidCon updates status: "Completed"
    ↓
VidCon sets actual_end_time

Transcript processing completes
    ↓
Google publishes: transcript.v2.fileGenerated
    ↓
Pub/Sub → VidCon webhook
    ↓
VidCon downloads transcript from Drive
    ↓
VidCon stores transcript (read-only)
    ↓
VidCon updates status: "Transcript Retrieved"
```

### Subscription Setup Flow
```
User opens VidCon Settings
    ↓
User selects Google Calendar
    ↓
User enters meeting_organizer_email
    ↓
User checks "Enable Meet Events"
    ↓
User clicks Save
    ↓
VidCon validates configuration
    ↓
VidCon calls create_meet_subscription()
    ↓
Google Workspace Events API creates subscription
    ↓
VidCon stores subscription_id
    ↓
VidCon displays status: "ACTIVE"
    ↓
Setup complete - no manual steps needed
```

## Data Matching Strategy

### How Events Match to Meetings

**Problem**: Pub/Sub events contain conference_id or space_id, but VidCon Meeting is created before the conference starts.

**Solution**:

1. **When Meeting Created**:
   - Extract `space_id` from Meet link: `https://meet.google.com/abc-defg-hij` → `abc-defg-hij`
   - Store in `google_space_id` field

2. **When conference.started Event Received**:
   - Event contains `conferenceRecord.name` = `conferenceRecords/xyz123`
   - Event contains `conferenceRecord.space` = `spaces/abc-defg-hij`
   - Match by space_id to find VidCon Meeting
   - Store `conference_id` = `xyz123` in VidCon Meeting

3. **For All Subsequent Events**:
   - Match by `conference_id` (faster, more reliable)

### Matching Logic

```python
def find_meeting_by_event(event_data):
    conference_record = event_data.get('conferenceRecord', {})
    conference_id = conference_record.get('name', '').split('/')[-1]
    space = conference_record.get('space', '').split('/')[-1]
    
    # Try matching by conference_id first (if meeting already started)
    meeting = frappe.db.get_value(
        "VidCon Meeting",
        {"google_conference_id": conference_id},
        "name"
    )
    
    if not meeting and space:
        # Fall back to matching by space_id
        meeting = frappe.db.get_value(
            "VidCon Meeting",
            {"google_space_id": space},
            "name"
        )
    
    return meeting
```

## Error Handling

### Subscription Creation Failures
- **OAuth not authorized**: Show clear error message with re-auth link
- **Pub/Sub topic not found**: Guide user to create topic
- **Insufficient permissions**: List required scopes

### Event Processing Failures
- **Meeting not found**: Log warning, don't fail (might be external meeting)
- **Transcript download fails**: Retry with exponential backoff
- **Participant data incomplete**: Create attendee with available data

### Recovery Mechanisms
- **Subscription expires/suspended**: Auto-recreate on next settings save
- **Missed events**: Scheduled task checks for completed meetings without transcripts
- **Duplicate events**: Use idempotency keys to prevent duplicate processing

## Security Considerations

1. **Webhook Authentication**: Validate Pub/Sub message signatures
2. **OAuth Tokens**: Encrypted storage, never logged
3. **Transcript Access**: Read-only fields, permission-controlled
4. **API Quotas**: Rate limiting, error handling

## Performance Optimizations

1. **Event Processing**: Async queue for all event handlers
2. **Database Queries**: Index on google_conference_id and google_space_id
3. **Transcript Storage**: Store in database (small files) or File doctype (large files)
4. **Caching**: Cache subscription status, avoid repeated API calls

## Testing Strategy

### Unit Tests
- Subscription creation/deletion
- Event matching logic
- Participant tracking
- Transcript download

### Integration Tests
- End-to-end meeting flow
- Pub/Sub message handling
- Google API interactions

### Manual Testing Checklist
- [ ] Create meeting in VidCon
- [ ] Verify Meet link generated
- [ ] Join meeting with 2+ participants
- [ ] Verify participant tracking
- [ ] End meeting
- [ ] Verify status updated to "Completed"
- [ ] Enable transcript in Meet
- [ ] Wait for transcript generation
- [ ] Verify transcript auto-downloaded
- [ ] Verify transcript is read-only

## Deployment Checklist

### Google Cloud Setup
- [ ] Enable Google Meet API
- [ ] Enable Google Workspace Events API
- [ ] Enable Google Drive API
- [ ] Create Pub/Sub topic: `meet-events`
- [ ] Grant publisher role to `meet-api-event-push@system.gserviceaccount.com`
- [ ] Create push subscription to VidCon webhook

### OAuth Configuration
- [ ] Add scopes:
  - `https://www.googleapis.com/auth/calendar`
  - `https://www.googleapis.com/auth/meetings.space.readonly`
  - `https://www.googleapis.com/auth/drive.readonly`
- [ ] Re-authorize Google Calendar

### VidCon Configuration
- [ ] Configure VidCon Settings
- [ ] Set meeting organizer email
- [ ] Enable Meet Events
- [ ] Verify subscription created
- [ ] Test with sample meeting

## Future Enhancements

1. **Multiple Organizers**: Support subscriptions for multiple users
2. **Recording Download**: Auto-download meeting recordings
3. **Smart Notes**: Support for Gemini AI notes (when available)
4. **Analytics**: Meeting duration, attendance metrics
5. **CRM Integration**: Auto-link meetings to Deals/Leads
6. **Notifications**: Email/Slack alerts for meeting events
