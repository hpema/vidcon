#!/bin/bash

# Test VidCon Webhook with Realistic Google Pub/Sub Message
# This simulates what Google sends when a conference ends

# Note: This will still fail JWT verification because we can't generate
# a valid Google-signed JWT, but it will test the full webhook flow
# and you'll see detailed logs in Error Log

# Conference ended event data (base64 encoded)
# Original JSON:
# {
#   "conferenceRecord": {
#     "name": "conferenceRecords/test-conference-123",
#     "space": "spaces/yqb-makz-vwf",
#     "startTime": "2026-03-22T13:00:00Z",
#     "endTime": "2026-03-22T14:00:00Z"
#   }
# }

EVENT_DATA='eyJjb25mZXJlbmNlUmVjb3JkIjp7Im5hbWUiOiJjb25mZXJlbmNlUmVjb3Jkcy90ZXN0LWNvbmZlcmVuY2UtMTIzIiwic3BhY2UiOiJzcGFjZXMveXFiLW1ha3otdndmIiwic3RhcnRUaW1lIjoiMjAyNi0wMy0yMlQxMzowMDowMFoiLCJlbmRUaW1lIjoiMjAyNi0wMy0yMlQxNDowMDowMFoifX0='

# Fake JWT token (will fail verification but tests the flow)
FAKE_JWT="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhdWQiOiJodHRwczovL3d3dy5wZW1hLmNvLnphL2FwaS9tZXRob2QvdmlkY29uLnZpZGNvbi5kb2N0eXBlLnZpZGNvbl9tZWV0aW5nLmdvb2dsZV9tZWV0X2V2ZW50cy5oYW5kbGVfcHVic3ViX3B1c2giLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJleHAiOjk5OTk5OTk5OTl9.fake-signature"

echo "Testing VidCon Webhook with Conference Ended Event"
echo "=================================================="
echo ""
echo "Event Type: google.workspace.meet.conference.v2.ended"
echo "Space ID: yqb-makz-vwf"
echo "Conference ID: test-conference-123"
echo ""
echo "Sending request..."
echo ""

curl -X POST https://www.pema.co.za/api/method/vidcon.vidcon.doctype.vidcon_meeting.google_meet_events.handle_pubsub_push \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${FAKE_JWT}" \
  -d "{
    \"message\": {
      \"data\": \"${EVENT_DATA}\",
      \"attributes\": {
        \"ce-type\": \"google.workspace.meet.conference.v2.ended\",
        \"ce-source\": \"//meet.googleapis.com/spaces/yqb-makz-vwf\",
        \"ce-subject\": \"conferenceRecords/test-conference-123\",
        \"ce-id\": \"test-event-123\"
      },
      \"messageId\": \"test-message-123\",
      \"publishTime\": \"2026-03-22T14:00:00Z\"
    },
    \"subscription\": \"projects/test-project/subscriptions/meet-events-push\"
  }" \
  -w "\n\nHTTP Status: %{http_code}\n"

echo ""
echo "=================================================="
echo "Check Error Log in Frappe for detailed logs:"
echo "1. Go to Error Log list"
echo "2. Look for entries with timestamps from now"
echo "3. You should see:"
echo "   - 🔔 Pub/Sub Webhook Called"
echo "   - 📋 Request Headers"
echo "   - 📦 Raw Request Body"
echo "   - 🔑 JWT Token Received"
echo "   - ❌ JWT Verification Failed (expected - fake token)"
echo ""
echo "If you see these logs, your webhook is working!"
echo "The JWT verification will fail (expected) but you'll see"
echo "all the logging we added."
echo "=================================================="
