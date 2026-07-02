# AssetIQ — Phase 00: Foundation & Shared Contracts

**Track:** Shared (must merge before 01–05 begin coding)
**Depends on:** —
**Gate:** none

## Objective

Freeze every interface the parallel tracks share, and scaffold a running-but-empty monorepo. After
this phase, five teammates can build against stable contracts without colliding. This spec defines:
repo layout, SQLite schema, the REST/OpenAPI contract, `.env` keys, the currency/FX rule, and the
data dictionary.

## Produces (the contracts everyone consumes)

### 1. Repo layout

```
Clorox_Mercedes_26/
├─ backend/
│  ├─ app/
│  │  ├─ main.py             FastAPI app, CORS, router registration, /health
│  │  ├─ config.py           pydantic-settings; loads .env (Settings singleton)
│  │  ├─ db.py               SQLAlchemy engine/session (SQLite), get_session dep
│  │  ├─ schemas.py          Pydantic request/response models (the API contract)
│  │  ├─ orm.py              SQLAlchemy table models
│  │  ├─ routers/            valuation, market, telemetry, diagnostics, vehicle, booking
│  │  └─ services/           predictor, market, obd_sim, odx_service, telegram_bot, calendar_agent
│  ├─ ml/                    ingest.py, train.py, evaluate.py, artifacts/ (gitignored)
│  ├─ scraper/               base.py, mudah.py, carlist.py, pipeline.py, fixtures/
│  ├─ tests/                 pytest (per-phase teammates add here)
│  ├─ pyproject.toml         deps + tool config
│  └─ requirements.txt
├─ frontend/
│  ├─ public/models/         drop AMG-GT .glb here; else procedural fallback
│  ├─ src/
│  │  ├─ main.tsx, App.tsx
│  │  ├─ scene/              Three.js: CarModel, loaders, fallback, controls, highlights
│  │  ├─ components/         SideNav, ComponentPanel, ValueHeader, DepreciationChart, ...
│  │  ├─ api/                typed client + MSW mock handlers
│  │  ├─ hooks/, styles/, types/
│  ├─ tests/                 playwright (Phase 06) + vitest component tests
│  ├─ package.json, vite.config.ts, tsconfig.json
├─ data/                     assetiq.db (gitignored), sample_odx/ (committed sample files)
├─ docs/superpowers/specs/
├─ .env.example              placeholder keys only (committed)
├─ .env                      real secrets (gitignored)
└─ README.md
```

### 2. SQLite schema (`backend/app/orm.py`)

`DATABASE_URL` (from `.env`, default `sqlite:///./data/assetiq.db`) is the single connection source.
**The connection string is never printed, logged, or returned by any endpoint.**

- **`training_data`** — cleaned `merc.csv`, prices in RM.
  `id PK · model · year · age · price_rm · transmission · mileage · fuel_type · tax · mpg ·
  engine_size · source ('merc.csv') · ingested_at`
- **`market_listings`** — real scraped listings (Mercedes only), prices in RM.
  `id PK · source ('mudah'|'carlist') · listing_url UNIQUE · model · variant · year · price_rm ·
  mileage · transmission · fuel_type · location · seller_type · posted_at · scraped_at`
  > **TODO(P00/P01):** enumerate the `seller_type` value set (e.g. `'dealer'|'private'|'unknown'`) and confirm `posted_at` storage type (ISO date string vs. relative "3 days ago" needing normalisation at scrape time — resolve at Gate 1).
- **`vehicle_profiles`** — the subject car(s) being valued.
  `id PK · name · model (must ∈ training_data.model set) · year · mileage · transmission ·
  fuel_type · engine_size · service_history_count · service_history_total · service_history_max ·
  workshop · glb_asset · created_at · updated_at`
- **`bookings`** — inspection bookings.
  `id PK · profile_id FK · name · workshop · car_model · purpose · date · time ·
  status ('pending'|'sent'|'confirmed'|'booked'|'failed'|'dry_run') · telegram_message_id ·
  calendar_event_id · created_at · updated_at`
- **`dtc_codes`** — cache of ODX-parsed fault-code definitions.
  `code PK · description · severity · system · source_odx`

### 3. REST / OpenAPI contract (`backend/app/schemas.py`)

All monetary values are RM integers. Endpoints and JSON shapes (Phase 03 implements; Phase 04
builds against these; both may generate types from the live OpenAPI at `/openapi.json`):

> **TODO(P00):** decide the TS type-generation approach for the frontend — `openapi-typescript` against `/openapi.json` (single source of truth, recommended) vs. hand-maintained `src/types/`. Pin the choice so Phase 04 doesn't drift from the contract.

| Method | Path | Request | Response (200) |
|--------|------|---------|----------------|
| GET | `/health` | — | `{status, version}` |
| POST | `/predict` | `VehicleProfileIn` | `{value_rm, low_rm, high_rm, confidence, currency:"RM"}` |
| GET | `/market/comps?model&year&limit` | query | `{comps:[MarketListing], median_rm, delta_pct, n}` |
| GET | `/depreciation?profile_id&years` | query | `{points:[{year, value_rm, retained_pct}]}` |
| GET | `/obd/snapshot?profile_id` | query | `{rpm, coolant_c, battery_v, health, odo_km, simulated:true, ts}` |
| GET | `/obd/stream?profile_id` | SSE | stream of the snapshot shape |
| GET | `/odx/faults?profile_id` | query | `{faults:[{code, description, severity, system}]}` |
| GET | `/vehicle/profile?id` | query | `VehicleProfileOut` |
| PUT | `/vehicle/profile` | `VehicleProfileIn` | `VehicleProfileOut` |
| POST | `/booking` | `BookingIn` | `{booking_id, status, dispatched:bool, dry_run:bool}` |

`VehicleProfileIn = {model, year, mileage, transmission, fuel_type, engine_size, mpg?, tax?,
service_history_count?, service_history_total?}`.
`BookingIn = {profile_id, name, workshop, car_model, purpose, date, time}`.
`MarketListing = {source, listing_url, model, variant?, year, price_rm, mileage, location, posted_at}`.

**Error contract:** JSON `{detail}` with 422 (validation), 404 (missing profile), 503 (model
artifact or dependency unavailable, with actionable message). No endpoint 500s from a missing
secret or missing optional data — see graceful-degradation rules in Phase 03.

### 4. `.env` keys (`.env.example` committed with placeholders only)

```
DATABASE_URL=sqlite:///./data/assetiq.db      # never printed/logged
FX_GBP_TO_RM=5.90                              # single source of truth for currency
CORS_ORIGINS=http://localhost:5173
SCRAPER_USER_AGENT=AssetIQResearchBot/0.1 (+contact)
SCRAPER_RATE_LIMIT_SECONDS=4
TELEGRAM_BOT_TOKEN=                             # phase 05
TELEGRAM_CHAT_ID=                              # phase 05
GEMINI_API_KEY=                                # phase 05
GOOGLE_CALENDAR_CREDENTIALS_JSON=./secrets/google_sa.json   # phase 05
GOOGLE_CALENDAR_ID=primary                     # phase 05
```

`config.py` exposes these via a typed `Settings` object. Any code that needs `DATABASE_URL` reads it
through `Settings`; it must never be interpolated into a log line or response. A unit test asserts
the string `sqlite` / connection URL never appears in `/health` or logs.

### 5. Currency / FX rule

FX conversion happens in exactly one place: `ml/ingest.py` multiplies `merc.csv` GBP prices by
`FX_GBP_TO_RM` to produce `price_rm` in `training_data`. Scraped listings are already RM. The model
trains and predicts in RM. Display is RM everywhere. Documented caveat (repeated in Phase 02):
converted prices reflect UK price *levels* in RM and may diverge from scraped MY listings; the FX
rate is tunable to calibrate.

### 6. Data dictionary

`merc.csv` raw columns: `model, year, price(GBP), transmission, mileage, fuelType, tax(UK road tax),
mpg(UK), engineSize`. Known dirty rows: leading spaces in `model`; inconsistent casing
(`SL CLASS` vs `SL Class`); a handful of numeric-only model rows (`230/220/200/180`). Cleaning
rules are owned by Phase 01.

## Tasks

1. Initialise `backend/` (FastAPI, SQLAlchemy, pydantic-settings, pytest) and `frontend/`
   (Vite + React + TS, three, @react-three/fiber, @react-three/drei, MSW, vitest, playwright).
   > **TODO(P00):** pin exact dependency versions (Python `requirements.txt`/`pyproject` + npm `package.json`) so all five parallel tracks build against identical toolchains. Note Python version for `odxtools` compatibility.
2. Implement `config.py`, `db.py`, `orm.py` (all tables), `schemas.py` (all models above), `main.py`
   with `/health` and CORS.
3. Write `.env.example`; extend `.gitignore` for `.env`, `data/*.db`, `backend/ml/artifacts/`,
   `secrets/`.
4. Create `data/sample_odx/` with a committed sample ODX/PDX file for Phase 03.
   > **TODO(P00):** obtain a **real** ODX/PDX file (from the `mercedes-benz/odxtools` example data or an equivalent public source) and commit it. Blocks Phase 03 `/odx/faults`. Do not hand-author fault codes.
5. Add root `README.md` (run instructions) and dev scripts (`make dev` / npm scripts).

## Tests (PyTest)

- App boots; `GET /health` returns 200 `{status:"ok"}`.
- All ORM tables create against a temp SQLite file.
- Every schema in the contract table imports and validates a sample payload.
- Secret-safety test: `DATABASE_URL` value never appears in `/health` response or captured logs.

## Done criteria

- `uvicorn` serves `/health`; `npm run dev` serves an empty themed shell that calls `/health`.
- All tables + all Pydantic schemas exist and import.
- `.env.example` committed; real `.env` gitignored; no secret in git.
- OpenAPI JSON at `/openapi.json` reflects the full contract table above.
