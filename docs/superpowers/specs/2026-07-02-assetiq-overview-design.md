# AssetIQ — Design Overview & Phase Index

**Product:** AssetIQ — a second-hand valuation & health dashboard for Mercedes-Benz. It predicts a
used car's resale value from (a) a model trained on the `merc.csv` dataset, (b) live second-hand
market data scraped from Malaysian marketplaces (Mudah.my, Carlist.my), and (c) OBD-II / ODX
vehicle data. It visualises the car in an interactive 3D dashboard and automates booking a
certified inspection via Telegram → Google Calendar.

**Date:** 2026-07-02
**Status:** Approved for planning
**Decomposition:** 7 parallel-executable phase specs (this document is the index).

---

## Global decisions (locked during brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Build structure | One product, **7 phase specs** run in parallel by different teammates |
| 2 | Currency | **Convert `merc.csv` GBP → RM before training** via a single configurable FX rate. Predictions therefore reflect *UK price levels expressed in RM* — a known, documented caveat; the FX rate stays tunable |
| 3 | Scraper | **Polite, robots-aware, rate-limited** scraper. At Gate 1 we attempt a live sample run and store **only real listings**. If blocked, we store what real data we captured — **never synthetic fills** |
| 4 | OBD-II / ODX | **Simulated** OBD-II telemetry stream (clearly labelled), **real** ODX fault-code parsing via `mercedes-benz/odxtools` on sample ODX/PDX files |
| 5 | Calendar agent | **Gemini** agent interprets the Telegram confirmation and books via Google Calendar API; **deterministic fallback** books from structured form data when keys are absent |
| 6 | 3D asset | Load `.glb` from `frontend/public/models/`; if absent, **procedurally build a low-poly coupe**. Idle auto-rotate + drag-orbit + scroll-zoom + clickable component highlights on both |
| 7 | ML scope | **Random Forest** (production) + **Linear Regression** (baseline), both scored by **GroupKFold(groups=model)** on **MAE, MAPE, RMSE, R²** |

> **TODO(cross-cutting/Gate1→2):** calibrate `FX_GBP_TO_RM` against the median RM of scraped comps once Gate-1 data lands, then re-run Phase 02 training. Owner: Data + ML.
> **TODO(cross-cutting/P00):** source and commit a **real** sample ODX/PDX file to `data/sample_odx/` (e.g. from the `odxtools` example data). No fabricated fault codes — Phases 00/03 depend on it.
> **TODO(cross-cutting/P05):** decide the source of "Nearest Mercedes Workshop" — a curated static list of real Mercedes-Benz Malaysia service centres vs. free-text user input. Must not be AI-invented. Consumed by the booking form (P04) and Telegram message (P05).

**Two authenticity rules that bind every phase:**
- No AI-invented market facts. If it isn't in `merc.csv` or scraped from Mudah.my / Carlist.my, it
  does not become a market number. Simulated OBD-II telemetry is device simulation (allowed) and is
  labelled as such, kept strictly separate from market data.
- Per-car adjustments not present in the data (e.g. the "+RM 15,300 full-service-history uplift" in
  the mockup) are **configurable, clearly-labelled assumptions**, never presented as market truth.

**Subject-vehicle vs. hero-model note:** `merc.csv` contains no "AMG GT". The 3D hero may remain an
AMG GT (or the low-poly coupe), but the *valued vehicle profile's* `model` field must be one of the
27 classes the model knows. Default sample profile uses a coupe-appropriate class present in the
data (**SL CLASS**), and is editable.

---

## Phase dependency graph

```
00-foundation      contracts + scaffold           ← LANDS FIRST, unblocks all
                        │
   ┌───────────┬────────┼────────────┬───────────────┐   ← run in PARALLEL against contracts
01-data        02-ml    03-backend   04-frontend      05-automation
scraper+ingest RF+LR    FastAPI      React+Three.js   Telegram+Gemini+Calendar
⛔ GATE 1      ⛔ GATE 2 (mocks)      (mock API)       (booking contract)
   └───────────┴────────┴────────────┴───────────────┘
                        │
              06-integration-and-e2e   ← LANDS LAST (real wiring + Playwright)
```

**Gates (mandatory human check-ins, requested by the product owner):**
- **Gate 1 (in Phase 01):** review scraper design, then review the live sample-run report before
  bulk scraping.
- **Gate 2 (in Phase 02):** review the RF-vs-LR metrics table before the model powers the dashboard.

**Parallelism rule:** Phase 00 must merge before 01–05 begin coding. Phases 01–05 then proceed
concurrently against the frozen contracts, each mocking any upstream piece that isn't ready. Phase
06 begins once 03/04/05 are functionally complete.

---

## Phase specs

| Spec | Owner track | Depends on | Gate |
|------|-------------|-----------|------|
| [00 — Foundation](2026-07-02-assetiq-00-foundation-design.md) | Shared | — | — |
| [01 — Data & Scraper](2026-07-02-assetiq-01-data-design.md) | Data | 00 | Gate 1 |
| [02 — ML Model](2026-07-02-assetiq-02-ml-design.md) | ML | 00 (schema) | Gate 2 |
| [03 — Backend API](2026-07-02-assetiq-03-backend-design.md) | Backend | 00, 02 (artifact contract) | — |
| [04 — Frontend Dashboard](2026-07-02-assetiq-04-frontend-design.md) | Frontend | 00 (API contract) | — |
| [05 — Automation](2026-07-02-assetiq-05-automation-design.md) | Automation | 00 (booking contract) | — |
| [06 — Integration & E2E](2026-07-02-assetiq-06-integration-design.md) | Integration | 01–05 | — |

## Tech stack (fixed by product owner)

Frontend: React + Three.js (Vite + TypeScript). Backend: FastAPI (Python). Database: SQLite.
Testing: PyTest (unit, per phase) + Playwright (E2E, Phase 06). ML: scikit-learn. Diagnostics:
`mercedes-benz/odxtools`. Automation: python-telegram-bot, Google Gemini SDK, Google Calendar API.

## Acceptance (maps to original requirements)

- [ ] Interactive 3D Mercedes hero (GLB or procedural fallback): idle spin, orbit, zoom, clickable
      components highlight + open the matching side-nav panel.
- [ ] Side nav: Engine & transmission, Battery/electrical, Mileage/odometer (OBD), Diagnostics
      fault codes (ODX), Fuel type & consumption, Service history, Brakes & suspension.
- [ ] Health-checkup button below the car producing an aggregate health score.
- [ ] RF price model + LR baseline, GroupKFold(by model), MAE/MAPE/RMSE/R² reported.
- [ ] Live market values scraped from Mudah.my + Carlist.my, Mercedes-only, in SQLite.
- [ ] Booking: Telegram message (Name, Workshop, Model, Purpose, Date, Time) → on confirmation →
      Gemini agent books Google Calendar (deterministic fallback).
- [ ] No AI-invented data; DB connection string never printed; secrets in `.env`.
- [ ] PyTest per phase + Playwright E2E.
