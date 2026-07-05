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
