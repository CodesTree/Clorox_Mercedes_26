# AssetIQ - Mercedes-Benz Resale Intelligence

Predicts a used Mercedes' resale value (RM) from a trained model, live Malaysian market
listings (Mudah.my / Carlist.my), and OBD-II/ODX vehicle data, in an interactive 3D dashboard.

Design docs: `docs/superpowers/specs/` (start with the overview).

## Prerequisites

- Python 3.11+, Node 22+
- `cp .env.example .env` (fill secrets later; everything degrades gracefully without them)

## Backend (FastAPI)

    cd backend
    python -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt   # Windows path; use .venv/bin on Unix
    cd ..
    backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload --port 8000

Run from the **repo root** so `./data/` and `.env` resolve correctly.
API docs: http://localhost:8000/docs . Contract: http://localhost:8000/openapi.json

### Google Calendar booking setup

Inspection bookings use a shared Google Calendar when service-account credentials are configured.
Do not commit the service account JSON or `.env`; both are local secrets.

1. Get the shared service account JSON from the team through a private channel.
2. Save it locally as `backend/secrets/google_sa.json`.
3. Copy `.env.example` to `backend/.env` if you have not already.
4. Set the Calendar values in `backend/.env`:

       GOOGLE_CALENDAR_CREDENTIALS_JSON=./secrets/google_sa.json
       GOOGLE_CALENDAR_ID=<shared_calendar_id>
       GOOGLE_CALENDAR_TIMEZONE=Asia/Kuala_Lumpur

5. In Google Calendar, share the calendar with the JSON file's `client_email` and allow it to make changes to events.
6. Restart the backend. A real Calendar booking returns `dry_run: false`; missing credentials return `dry_run: true` with `payload.calendar_error`.

## Booking agent (Telegram + Google Calendar)

The `/booking` flow sends an appointment proposal to Telegram, waits for a human reply, then books a
Google Calendar event. Config lives in the **repo-root `.env`** (loaded by `backend/app/config.py`):

    TELEGRAM_BOT_TOKEN=...            # BotFather token
    TELEGRAM_CHAT_ID=...             # chat the proposal is sent to
    GEMINI_API_KEY=...              # optional; reply-intent classification (keyword fallback if absent)
    GOOGLE_CALENDAR_CREDENTIALS_JSON=...   # service-account JSON (inline or file path) — creates + reads events
    GOOGLE_CALENDAR_ID=you@gmail.com       # the calendar to book on. NOT "primary" with a service account!
    GOOGLE_CALENDAR_TIMEZONE=Asia/Kuala_Lumpur

**Service-account calendar access (required for availability + booking to work):**

1. Set `GOOGLE_CALENDAR_ID` to the actual calendar address (e.g. your Gmail), **not** `primary` — with a
   service account, `primary` is the SA's own hidden calendar, so it would always show "free" and create
   events you can't see.
2. Share that calendar with the service account's `client_email`, granting **"Make changes to events"**
   (Google Calendar → Settings for my calendars → Share with specific people). This one grant enables
   both free/busy reads and event creation.

**Verify configuration** (no secrets are returned):

    GET http://localhost:8000/booking/diagnostics

It reports which integrations are configured, whether Telegram has a webhook configured
(`telegram_webhook_configured`), the `calendar_id`, the `service_account_email` to share with, and a
live `freebusy_probe` (`ok` or the error). If `telegram_webhook_configured` is `true`, Telegram polling
via `getUpdates` will not see replies reliably; remove the webhook or move the app to a webhook-based
inbound route.

When the backend polls replies through `POST /booking/{id}/check-reply`, it stores the last Telegram
`update_id` per booking and uses it as the next `getUpdates` offset. Proposal messages include a
`BKG-<id>` booking reference. For multiple active bookings, ask the workshop to reply directly to the
Telegram proposal or include that booking reference so the backend can match the reply to the right
booking. All integrations degrade to dry-run / "assume free" when unconfigured, so the app never
hard-fails.

## Frontend (React + Three.js)

    cd frontend
    npm install
    npm run dev        # http://localhost:5173 (proxies /api -> :8000)

## Tests

    cd backend && .venv/Scripts/python -m pytest      # backend unit tests
    cd frontend && npm test                            # component smoke tests

## Repo layout

    backend/app       FastAPI app: config, db, orm, schemas, routers (contract), services
    backend/ml        ingest/train/evaluate (Phase 02)
    backend/scraper   Mudah/Carlist polite scraper (Phase 01)
    frontend/         Vite + React + TS dashboard (Phase 04)
    data/sample_odx   real odxtools example PDX (consumed by Phase 03)
    docs/superpowers  specs and plans

Secrets live in `.env` (gitignored). The DB connection string is never printed or logged.
