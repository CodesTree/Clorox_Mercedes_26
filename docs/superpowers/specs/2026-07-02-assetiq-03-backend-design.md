# AssetIQ — Phase 03: Backend API (FastAPI)

**Track:** Backend
**Depends on:** 00 (contract, schema), 02 (predictor interface — mock until artifact lands).
**Gate:** none

## Objective

Implement the REST/SSE contract from Phase 00. Thin routers delegate to focused services. Every
external dependency degrades gracefully — nothing 500s from a missing secret or missing data.

## Consumes

- Phase 00 `schemas.py`, `orm.py`, `config.py`, `db.py`.
- Phase 02 predictor interface. Until `model.joblib` exists, `predictor` returns 503 with an
  actionable message; contract tests use a stub predictor.

## Produces

Routers + services implementing:

| Endpoint | Service | Notes |
|----------|---------|-------|
| `POST /predict` | `predictor.py` | loads `model.joblib`; RM value + 92% band; 503 if no artifact |
| `GET /market/comps` | `market.py` | query `market_listings` by model/year window; `median_rm`, `delta_pct` vs `/predict`; `comps:[]` if none |
| `GET /depreciation` | `predictor.py` | model-derived retained-value curve |
| `GET /obd/snapshot` | `obd_sim.py` | simulated telemetry, `simulated:true` always set |
| `GET /obd/stream` | `obd_sim.py` | Server-Sent Events stream of snapshots |
| `GET /odx/faults` | `odx_service.py` | `odxtools` parses `data/sample_odx/*`; caches to `dtc_codes` |
| `GET/PUT /vehicle/profile` | `vehicle.py` | CRUD on `vehicle_profiles`; seeds a default SL CLASS profile |
| `POST /booking` | booking router | validates, persists `bookings`, delegates to automation interface (Phase 05); returns dry-run payload if automation/keys absent |

**`obd_sim.py`:** generates physics-plausible values — RPM idle/rev band, coolant warm-up curve,
battery 12.4–14.4 V, health 0–100 from a simple weighted function of simulated signals + fault
count + service completeness. Deterministic seed option for tests. Always labelled simulated.

**`odx_service.py`:** uses `mercedes-benz/odxtools` to read the committed sample ODX/PDX file into
`{code, description, severity, system}`; cache to `dtc_codes`. If the sample file is missing, return
`faults:[]` (no crash).

**`market.py`:** `delta_pct = (predict_value − median_comp) / median_comp`. Both sides RM. If no
comps for the model/year window, return `comps:[], median_rm:null, delta_pct:null`.

**Booking interface:** backend defines `BookingDispatcher` protocol; ships a `DryRunDispatcher`
(returns the exact payload it would send, `dry_run:true`). Phase 05 provides the real Telegram
dispatcher; wiring is a config swap.

## Graceful-degradation rules (must hold)

- No `model.joblib` → `/predict`, `/depreciation` return 503 `{detail:"train model first: python -m ml.train"}`.
- Empty `market_listings` → `/market/comps` returns empty comps, UI hides the delta.
- Missing sample ODX → `/odx/faults` returns `faults:[]`.
- Missing Telegram/Gemini/Google keys → `/booking` persists + returns `dry_run:true`, never errors.
- `DATABASE_URL` never appears in any response or log line.

## Tests (PyTest, FastAPI `TestClient`)

- Contract test per endpoint: request/response match `schemas.py`.
- `/predict` with stub predictor returns the band shape; with no artifact returns 503.
- `obd_sim` values fall in declared ranges; `simulated:true` always present.
- `odx_service` parses the sample file into ≥1 fault; missing file → `[]`.
- `/market/comps` computes `delta_pct` correctly; empty DB → nulls.
- `/booking` dry-run persists a row and returns the payload; no secret leaks in logs.

## Done criteria

- `uvicorn` serves the full contract; `/openapi.json` matches Phase 00.
- All degradation rules verified by tests.
- Runs standalone with a stub predictor + `DryRunDispatcher` (no ML artifact, no secrets required).
