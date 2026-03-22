# CallSpark AI Backend

A working starter backend for an HVAC missed-call recovery AI.

It includes:
- Twilio missed-call webhook
- Twilio inbound SMS webhook
- OpenAI lead qualification logic
- Supabase lead and message logging
- hard-rule escalation for dangerous issues
- a simple daily reporting endpoint

## What this does
When a lead calls and nobody answers, this app can:
1. create a lead record
2. text them back instantly
3. ask one question at a time
4. extract structured fields from replies
5. escalate dangerous or angry conversations to a human
6. save everything to Supabase

## Stack
- FastAPI
- Twilio
- OpenAI API
- Supabase

## Files
- `app/main.py` - application code
- `schema.sql` - database tables
- `.env.example` - environment variables
- `requirements.txt` - Python dependencies

## Quick start
### 1) Create a Python environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Create your database tables
Run `schema.sql` in Supabase SQL Editor.

### 3) Configure env vars
```bash
cp .env.example .env
```
Then fill in your keys.

### 4) Start the server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5) Expose your local server to Twilio
Use ngrok or Cloudflare Tunnel.

Example:
```bash
ngrok http 8000
```

### 6) Configure Twilio webhooks
Use your public URL.

- SMS webhook: `POST /webhooks/twilio/sms`
- Missed call webhook: `POST /webhooks/twilio/voice-missed`

In practice, many teams wire the missed-call endpoint from a Twilio flow or status callback after an unanswered call.

## Suggested Twilio setup
### SMS
Point incoming message webhook to:
```text
https://your-domain.com/webhooks/twilio/sms
```

### Missed calls
A common first pass is:
- route inbound calls into Twilio Studio or Voice
- if no answer / voicemail / timeout, call the missed-call endpoint
- the backend sends the SMS follow-up

## API endpoints
### `GET /health`
Health check.

### `POST /webhooks/twilio/voice-missed`
Accepts Twilio form fields like `From` and `To` and sends the first missed-call SMS.

### `POST /webhooks/twilio/sms`
Handles inbound SMS, runs qualification, updates the lead, and replies.

### `POST /webhooks/webform`
Creates a lead from a website form and sends the first follow-up text.

### `POST /internal/qualify`
Runs the AI logic directly for testing.

### `POST /internal/report/daily`
Returns a simple aggregate summary for the current UTC day.

## Example test request
```bash
curl -X POST http://localhost:8000/internal/qualify \
  -H 'Content-Type: application/json' \
  -d '{
    "business_id":"YOUR_BUSINESS_ID",
    "channel":"sms",
    "latest_user_message":"My AC is not cooling and I am in 78704",
    "conversation_history":[]
  }'
```

## Expected model output shape
The OpenAI step should return JSON with:
- `next_message`
- `extracted_fields`
- `urgency`
- `intent`
- `should_escalate`
- `should_send_booking_link`
- `closing_reason`

## Important notes
- This is intentionally narrow. It is an AI receptionist, not a general chatbot.
- Dangerous issues should always escalate.
- Do not let the model make hard business decisions by itself.
- Start SMS-first. Add voice later.

## Production next steps
- add auth for internal endpoints
- sign Twilio webhook requests
- add retries and idempotency
- add observability and alerting
- add per-business prompt versions
- add better business-hours handling
- add opt-out and spam audit logging
