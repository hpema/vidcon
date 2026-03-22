#!/bin/bash

# Simple test - Conference Ended Event
# This uses your actual meeting's space ID: yqb-makz-vwf

echo "Testing Conference Ended Event for space: yqb-makz-vwf"
echo ""

curl -X POST https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhdWQiOiJodHRwczovL3d3dy5wZW1hLmNvLnphL2FwaS9tZXRob2QvdmlkY29uLnZpZGNvbi5kb2N0eXBlLnZpZGNvbl9tZWV0aW5nLmdvb2dsZV9tZWV0X2V2ZW50cy5oYW5kbGVfcHVic3ViX3B1c2giLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJleHAiOjk5OTk5OTk5OTl9.fake" \
  -d '{
    "message": {
      "data": "eyJjb25mZXJlbmNlUmVjb3JkIjp7Im5hbWUiOiJjb25mZXJlbmNlUmVjb3Jkcy90ZXN0LWNvbmZlcmVuY2UtMTIzIiwic3BhY2UiOiJzcGFjZXMveXFiLW1ha3otdndmIiwic3RhcnRUaW1lIjoiMjAyNi0wMy0yMlQxMzowMDowMFoiLCJlbmRUaW1lIjoiMjAyNi0wMy0yMlQxNDowMDowMFoifX0=",
      "attributes": {
        "ce-type": "google.workspace.meet.conference.v2.ended",
        "ce-source": "//meet.googleapis.com/spaces/yqb-makz-vwf",
        "ce-subject": "conferenceRecords/test-conference-123",
        "ce-id": "test-event-123"
      },
      "messageId": "test-msg-123",
      "publishTime": "2026-03-22T14:00:00Z"
    },
    "subscription": "projects/test/subscriptions/meet-events-push"
  }' \
  -w "\n\nHTTP Status: %{http_code}\n\n"

echo "Now check Error Log in Frappe for detailed logs!"
echo "You should see multiple entries with emojis showing the full flow."
