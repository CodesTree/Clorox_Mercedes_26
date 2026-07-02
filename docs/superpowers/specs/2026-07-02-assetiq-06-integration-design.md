# AssetIQ — Phase 06: Integration & End-to-End Testing

**Track:** Integration (lands last)
**Depends on:** 01–05 functionally complete.
**Gate:** none

## Objective

Wire the real pieces together, replace mocks/stubs with live implementations, and prove the whole
product works with Playwright E2E plus cross-phase integration tests.

## Consumes

- Real `model.joblib` (02), populated SQLite (01), live FastAPI (03), the React app (04), the real
  `TelegramDispatcher` + `calendar_agent` (05).

## Produces

- Integration test suite (PyTest) exercising real component seams.
- Playwright E2E suite (`frontend/tests/`).
- A short run/verify runbook in `README.md`.

## Wiring tasks

1. Point the frontend at the live backend (drop MSW for E2E runs).
2. Swap Phase 03's `DryRunDispatcher` for Phase 05's `TelegramDispatcher` via config.
3. Seed a default `vehicle_profiles` row (SL CLASS) and load `training_data`; run `ml.train` so
   `/predict` serves the real artifact.
4. Confirm `/market/comps` reads real scraped rows (from the Gate-1 sample) and computes the delta.

## Integration tests (PyTest)
- Real predictor: `/predict` returns a plausible RM band for the seeded profile.
- `/market/comps` returns real listings + a numeric `delta_pct`.
- `/odx/faults` returns parsed faults from the sample ODX.
- Booking end-to-end in dry-run: `POST /booking` → persisted → deterministic calendar event payload
  produced (mocked Google), without real secrets.

## Playwright E2E (`frontend/tests/`)
- Dashboard loads; 3D `<canvas>` mounts; idle spin observable.
- Each side-nav item opens its panel; a mesh click opens the same panel.
- Health-checkup button produces a score.
- Booking form submits and shows dry-run/dispatched state.
- Graceful states: model-not-trained placeholder, empty-comps hides delta, GLB-absent fallback.

## Done criteria
- Full stack runs locally: `uvicorn` + `npm run dev`, real data + real artifact.
- PyTest (all phases) green; Playwright E2E green.
- README runbook lets a new teammate start the whole app and reproduce the E2E run.
- Acceptance checklist in the overview spec fully ticked.
