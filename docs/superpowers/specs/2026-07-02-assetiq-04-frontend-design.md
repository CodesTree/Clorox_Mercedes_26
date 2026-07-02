# AssetIQ — Phase 04: Frontend Dashboard (React + Three.js)

**Track:** Frontend
**Depends on:** 00 (API contract). Builds against an **MSW mock** of the contract until Phase 03 is
live, so it can start immediately.
**Gate:** none

## Objective

A clean, premium 3D valuation dashboard that improves on the supplied mockup — deliberately not a
stock Three.js demo. Interactive Mercedes hero, component side-nav wired to the 3D model, and the
valuation/telemetry/booking surfaces.

## Consumes

- Phase 00 REST/SSE contract (typed client generated from `/openapi.json` or hand-typed in
  `src/types/`). MSW handlers in `src/api/` mock every endpoint for standalone dev + tests.

## Produces

### 3D scene (`src/scene/`)
- `CarModel`: loads `.glb` from `public/models/` via drei `useGLTF`. **If absent → procedurally
  build a low-poly coupe** (primitive body + wheels) so the app always renders.
- **Idle auto-rotate** ("microwave spin"): continuous slow Y-rotation that **pauses on user
  interaction and resumes after ~3 s idle**.
- **Controls:** drag-orbit + scroll-zoom (`OrbitControls`), sensible min/max zoom and polar limits.
- **Component highlighting:** raycaster maps hero meshes (or fallback proxies) to the 7 components;
  hovering/selecting highlights the region (emissive/outline) and opens the matching panel.
  Mesh-click and side-nav-click are the **same action**.
  > **TODO(P04):** define the mesh-name → component map for the AMG GT `.glb` (depends on the asset's node names) **and** the clickable proxy regions for the procedural fallback, so both hero variants map to all 7 components.

### Components (`src/components/`)
- `SideNav` — the 7 items: Engine & transmission · Battery/electrical · Mileage/odometer (OBD) ·
  Diagnostics fault codes (ODX) · Fuel type & consumption · Service history · Brakes & suspension.
- `ComponentPanel` — content per component, fed by the matching endpoint (OBD → `/obd/*`,
  Diagnostics → `/odx/faults`, etc.).
- `ValueHeader` — headline `value_rm`, `[low,high]` band, `confidence`, `delta_pct` vs market
  (hidden when null).
- `DepreciationChart` — `/depreciation` retained-value curve.
  > **TODO(P04):** choose the chart rendering approach (hand-rolled SVG vs. a lib e.g. Recharts/visx) — keep it dependency-light to match the premium, non-stock-demo aesthetic.
- `HealthCheck` — button below the car; aggregates telemetry + faults + service completeness into a
  health score (e.g. "87/100") with a short breakdown.
  > **TODO(P04):** consume the **shared** health-score formula defined in Phase 03 (do not re-invent it here); define the breakdown line items shown to the user. Confirm the idle-spin resume delay (~3 s).
- `ServiceHistory` — summary + the labelled **assumption** adjustment (never shown as market truth).
- `BookingModal` — form (Name, Nearest Workshop, Car model, Purpose, Date, Time) → `POST /booking`;
  shows dry-run vs dispatched state.

### Design system (`src/styles/`)
- Dark theme, teal accent, generous spacing, real type hierarchy; layout mirrors the mockup but
  cleaner: hero value top-center, live OBD-II rail left, valuation factors right, depreciation
  bottom-right, CTA center-bottom, service summary bottom-left. Live telemetry via SSE `/obd/stream`
  with graceful reconnect.
  > **TODO(P04):** define the concrete design tokens — exact palette (dark base + teal accent hex values), spacing scale, and type scale/fonts — as CSS variables/theme before building components, so the look is intentional and consistent, not ad-hoc.

## Graceful states
- Missing `.glb` → procedural coupe (no error).
- `/predict` 503 → "model not trained yet" placeholder in `ValueHeader`.
- Empty comps → hide the market delta.
- SSE unavailable → fall back to polling `/obd/snapshot`.

## Tests (Vitest + React Testing Library; Playwright E2E lives in Phase 06)
- Side-nav click opens the correct panel; mesh-select and nav-select stay in sync (mocked scene).
- `ValueHeader` renders band + hides delta when null.
- Booking form submits and reflects dry-run/dispatched.
- Health-checkup computes and displays a score from mocked data.
- Procedural fallback renders when no GLB is provided.

## Done criteria
- `npm run dev` renders the full dashboard against MSW mocks with no backend running.
- 3D hero: idle spin + orbit + zoom + clickable component highlights (GLB and fallback both).
- All panels wired to the contract; all graceful states handled.
