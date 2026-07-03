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
    .venv/Scripts/python -m playwright install chromium        # browser binary for live scraper runs
    cd ..
    backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload --port 8000

Run from the **repo root** so `./data/` and `.env` resolve correctly.
API docs: http://localhost:8000/docs . Contract: http://localhost:8000/openapi.json

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
