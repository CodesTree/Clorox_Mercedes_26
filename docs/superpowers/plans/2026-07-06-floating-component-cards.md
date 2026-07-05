# Floating Component Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single fixed bottom-left `ComponentDetail` card with a floating "callout" card that pops up at one of 3 fixed screen anchors (top-center, left-flank, lower-right) depending on which vehicle component is selected, fading in at its anchor each time the selection changes.

**Architecture:** A new `anchor` field on each entry in `COMPONENTS` (`componentConfig.ts`) maps every component to one of 3 anchors via `index % 3`. `ComponentDetail` renders the same content it does today, but its wrapping `<section>` gets a `component-callout component-callout--<anchor>` class and a `key={component.id}` so React remounts it on every selection change, replaying a CSS fade-in animation. `theme.css`'s single `.component-detail` position rule is replaced by a shared `.component-callout` base rule plus 3 modifier rules for the anchor coordinates.

**Tech Stack:** React 18 + TypeScript, Vite, Vitest + `@testing-library/react`, plain CSS (no new dependencies).

---

## Reference: spec

Full design rationale lives in `docs/superpowers/specs/2026-07-06-floating-component-cards-design.md`. This plan implements it directly — anchor positions and the component→anchor table below match that spec.

## File Structure

- Modify `frontend/src/components/componentConfig.ts` — add `anchor: "top" | "left" | "lower-right"` to `ComponentItem` and to all 7 entries.
- Create `frontend/src/components/componentConfig.test.ts` — asserts the anchor mapping.
- Modify `frontend/src/components/ComponentDetail.tsx` — rename `component-detail*` classes to `component-callout*`, add the anchor modifier class, add `key={component.id}`.
- Create `frontend/src/components/ComponentDetail.test.tsx` — asserts the rendered anchor class and that content is unchanged.
- Modify `frontend/src/styles/theme.css` — replace `.component-detail` rules with `.component-callout` + 3 anchor variants + fade-in animation; rename remaining `.component-detail*` references (font list, mobile media queries).
- Modify `frontend/src/scene/CarScene.test.ts` — update 3 assertions that check literal `theme.css` text against the old `.component-detail` selectors/values.

---

### Task 1: Add `anchor` field to component config

**Files:**
- Modify: `frontend/src/components/componentConfig.ts`
- Test: `frontend/src/components/componentConfig.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/componentConfig.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { COMPONENTS } from "./componentConfig";

describe("componentConfig anchors", () => {
  it("assigns each component one of 3 fixed anchors, by list order mod 3", () => {
    const expected: Record<string, "top" | "left" | "lower-right"> = {
      engine: "top",
      battery: "left",
      brakes: "lower-right",
      fuel: "top",
      mileage: "left",
      diagnostics: "lower-right",
      service: "top",
    };

    for (const component of COMPONENTS) {
      expect(component.anchor).toBe(expected[component.id]);
    }
  });

  it("only ever uses the 3 known anchor values", () => {
    const validAnchors = new Set(["top", "left", "lower-right"]);
    for (const component of COMPONENTS) {
      expect(validAnchors.has(component.anchor)).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/componentConfig.test.ts`
Expected: FAIL — `component.anchor` is `undefined`, so `expect(undefined).toBe("top")` fails (and the TypeScript compiler would also flag `anchor` as not existing on `ComponentItem` once the test imports typed data, but Vitest here runs via esbuild transpilation, so the test fails at the assertion, not at type-check time).

- [ ] **Step 3: Implement — add the `anchor` field**

In `frontend/src/components/componentConfig.ts`, update the interface:

```ts
export interface ComponentItem {
  id: ComponentId;
  code: string;
  label: string;
  shortLabel: string;
  value: string;
  sub: string;
  impact: string;
  positive: boolean;
  anchor: "top" | "left" | "lower-right";
}
```

Add `anchor` to each of the 7 entries in `COMPONENTS` (values per the table below — this is `COMPONENTS` array index `% 3`, where 0 → `"top"`, 1 → `"left"`, 2 → `"lower-right"`):

```ts
export const COMPONENTS: ComponentItem[] = [
  {
    id: "engine",
    code: "ENG",
    label: "Engine & transmission",
    shortLabel: "Engine",
    value: "4.0L V8 BiTurbo",
    sub: "Oil life 62% - 0 faults",
    impact: "+RM 18,400",
    positive: true,
    anchor: "top",
  },
  {
    id: "battery",
    code: "BAT",
    label: "Battery/electrical",
    shortLabel: "Battery",
    value: "12V system",
    sub: "SOH 94% - alternator OK",
    impact: "+RM 6,200",
    positive: true,
    anchor: "left",
  },
  {
    id: "brakes",
    code: "BRK",
    label: "Brakes & suspension",
    shortLabel: "Brakes",
    value: "Sport suspension",
    sub: "Rotor wear normal",
    impact: "+RM 4,900",
    positive: true,
    anchor: "lower-right",
  },
  {
    id: "fuel",
    code: "FUE",
    label: "Fuel type & consumption",
    shortLabel: "Fuel",
    value: "Petrol V8",
    sub: "Fuel trim within range",
    impact: "-RM 2,100",
    positive: false,
    anchor: "top",
  },
  {
    id: "mileage",
    code: "ODO",
    label: "Mileage/odometer (OBD)",
    shortLabel: "Odometer",
    value: "45,320 km",
    sub: "OBD agrees with profile",
    impact: "+RM 9,800",
    positive: true,
    anchor: "left",
  },
  {
    id: "diagnostics",
    code: "DTC",
    label: "Diagnostics fault codes",
    shortLabel: "Diagnostics",
    value: "ODX status report",
    sub: "1 informational signal",
    impact: "-RM 1,600",
    positive: false,
    anchor: "lower-right",
  },
  {
    id: "service",
    code: "SVC",
    label: "Service history",
    shortLabel: "Service",
    value: "6 of 7 records",
    sub: "Assumption adjustment only",
    impact: "+RM 11,200",
    positive: true,
    anchor: "top",
  },
];
```

Leave `getComponent` unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/componentConfig.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/componentConfig.ts frontend/src/components/componentConfig.test.ts
git commit -m "feat: assign each vehicle component a fixed callout anchor"
```

---

### Task 2: Point `ComponentDetail` at the anchor, rename its CSS hooks

**Files:**
- Modify: `frontend/src/components/ComponentDetail.tsx`
- Test: `frontend/src/components/ComponentDetail.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/ComponentDetail.test.tsx`:

```tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ComponentDetail } from "./ComponentDetail";

describe("ComponentDetail", () => {
  it("renders the battery card at its left anchor", () => {
    const { container } = render(
      <ComponentDetail selected="battery" profile={null} snapshot={null} faults={[]} market={null} />,
    );

    const card = container.querySelector(".component-callout");
    expect(card).not.toBeNull();
    expect(card).toHaveClass("component-callout--left");
    expect(card?.querySelector(".component-callout__code")?.textContent).toBe("BAT");
    expect(container.querySelector(".component-detail")).toBeNull();
  });

  it("renders the engine card at its top anchor", () => {
    const { container } = render(
      <ComponentDetail selected="engine" profile={null} snapshot={null} faults={[]} market={null} />,
    );

    expect(container.querySelector(".component-callout--top")).not.toBeNull();
  });

  it("renders the brakes card at its lower-right anchor", () => {
    const { container } = render(
      <ComponentDetail selected="brakes" profile={null} snapshot={null} faults={[]} market={null} />,
    );

    expect(container.querySelector(".component-callout--lower-right")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ComponentDetail.test.tsx`
Expected: FAIL — `.component-callout` is not found (component still renders `.component-detail`).

- [ ] **Step 3: Implement — rename classes, add anchor modifier and remount key**

In `frontend/src/components/ComponentDetail.tsx`, replace the `return (...)` block:

```tsx
  return (
    <section
      key={component.id}
      className={`component-callout component-callout--${component.anchor}`}
      aria-label="Selected component detail"
    >
      <div className="component-callout__code">{component.code}</div>
      <div className="component-callout__main">
        <h2>{component.label}</h2>
        {selected === "engine" ? (
          <p>
            {profile?.engine_size.toFixed(1) ?? "--"}L {profile?.fuel_type ?? "powertrain"} -{" "}
            {snapshot ? `${snapshot.rpm} rpm` : "OBD pending"} - {profile?.transmission ?? "transmission pending"}
          </p>
        ) : null}
        {selected === "battery" ? (
          <p>
            Battery voltage {snapshot ? `${snapshot.battery_v.toFixed(1)} V` : "pending"} - coolant{" "}
            {snapshot ? `${Math.round(snapshot.coolant_c)} C` : "pending"}
          </p>
        ) : null}
        {selected === "brakes" ? (
          <p>
            Brakes and suspension inferred from health score {snapshot?.health ?? "--"}/100 and diagnostic signals.
          </p>
        ) : null}
        {selected === "fuel" ? (
          <p>
            {profile?.fuel_type ?? "Fuel type pending"} - {profile?.mpg ? `${profile.mpg} mpg` : "consumption pending"}
          </p>
        ) : null}
        {selected === "mileage" ? (
          <p>
            {snapshot ? snapshot.odo_km.toLocaleString() : "--"} km from OBD - profile{" "}
            {profile ? profile.mileage.toLocaleString() : "--"} km
          </p>
        ) : null}
        {selected === "diagnostics" ? (
          <div className="fault-summary">
            {faults.length ? (
              faults.map((fault) => (
                <p key={fault.code}>
                  <strong>{fault.code}</strong> - {fault.description} - {fault.severity} - {fault.system}
                </p>
              ))
            ) : (
              <p>No ODX faults returned</p>
            )}
          </div>
        ) : null}
        {selected === "service" ? (
          <p>
            {profile?.service_history_count ?? 0}/{profile?.service_history_total ?? profile?.service_history_max ?? "?"}{" "}
            records captured. Assumption adjustment only, not market truth.
          </p>
        ) : null}
        {selected !== "diagnostics" ? (
          <p className="component-callout__sub">
            {component.value} - {component.sub}
            {market?.median_rm ? ` - Market median ${formatRm(market.median_rm)}` : ""}
          </p>
        ) : null}
      </div>
      <strong className={`component-callout__impact ${impactClass}`}>{component.impact}</strong>
    </section>
  );
```

Nothing else in the file changes — props, `getComponent`, `impactClass`, and every conditional branch stay exactly as they are today.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ComponentDetail.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ComponentDetail.tsx frontend/src/components/ComponentDetail.test.tsx
git commit -m "feat: render ComponentDetail as an anchored callout card"
```

---

### Task 3: Replace the fixed card position in `theme.css` with 3 anchor variants

**Files:**
- Modify: `frontend/src/styles/theme.css`
- Modify: `frontend/src/scene/CarScene.test.ts`

- [ ] **Step 1: Update the existing CSS-text assertions so they expect the new selectors (write the failing test first)**

In `frontend/src/scene/CarScene.test.ts`, in the `"dashboard typography is sized for presentation viewing"` test, change:

```ts
  expect(themeCss).toMatch(/\.component-detail p\s*{[^}]*font-size:\s*12px;/s);
```
to:
```ts
  expect(themeCss).toMatch(/\.component-callout p\s*{[^}]*font-size:\s*12px;/s);
```

In the `"dashboard visual system matches Claude cinematic stage v2"` test, replace these two lines:
```ts
  expect(themeCss).toMatch(/\.component-detail,\s*\.depreciation-panel,\s*\.booking-modal\s*{[^}]*border-radius:\s*16px;/s);
  expect(themeCss).toMatch(/\.dock-button\s*{[^}]*border-radius:\s*14px;/s);
  expect(themeCss).toMatch(/\.component-detail\s*{[^}]*left:\s*26px;[^}]*bottom:\s*26px;/s);
```
with:
```ts
  expect(themeCss).toMatch(/\.component-callout,\s*\.depreciation-panel,\s*\.booking-modal\s*{[^}]*border-radius:\s*16px;/s);
  expect(themeCss).toMatch(/\.dock-button\s*{[^}]*border-radius:\s*14px;/s);
  expect(themeCss).toMatch(/\.component-callout--top\s*{[^}]*left:\s*50%;/s);
  expect(themeCss).toMatch(/\.component-callout--left\s*{[^}]*left:\s*14%;/s);
  expect(themeCss).toMatch(/\.component-callout--lower-right\s*{[^}]*right:\s*8%;/s);
```

Add one new test at the end of the file asserting the 3 anchors exist with their full expected coordinates and that the fade-in animation is wired up:

```ts
test("component callout cards anchor to 3 fixed points and fade in", () => {
  expect(themeCss).toMatch(/@keyframes callout-in\s*{[^}]*opacity:\s*0;/s);
  expect(themeCss).toMatch(/\.component-callout\s*{[^}]*animation:\s*callout-in\s+180ms\s+ease-out;/s);
  expect(themeCss).toMatch(/\.component-callout--top\s*{[^}]*top:\s*14%;[^}]*left:\s*50%;[^}]*transform:\s*translateX\(-50%\);/s);
  expect(themeCss).toMatch(/\.component-callout--left\s*{[^}]*top:\s*48%;[^}]*left:\s*14%;/s);
  expect(themeCss).toMatch(/\.component-callout--lower-right\s*{[^}]*top:\s*66%;[^}]*right:\s*8%;/s);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/scene/CarScene.test.ts`
Expected: FAIL on the 3 updated assertions plus the new test — `theme.css` still has `.component-detail`, not `.component-callout`, and no `--top`/`--left`/`--lower-right` variants or `callout-in` keyframe exist yet.

- [ ] **Step 3: Implement — update `theme.css`**

In `frontend/src/styles/theme.css`, in the font-family selector list (currently starting at the line with `.eyebrow,`), change:

```css
.eyebrow,
.panel-heading,
.rail-title,
.telemetry-stat span,
.component-detail__code,
.value-header__band,
```
to:
```css
.eyebrow,
.panel-heading,
.rail-title,
.telemetry-stat span,
.component-callout__code,
.value-header__band,
```

Replace the whole block from the shared panel rule through `.component-detail__impact` (currently):

```css
.component-detail,
.depreciation-panel,
.booking-modal {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  backdrop-filter: blur(12px);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.42), inset 0 0 0 1px rgba(0, 210, 190, 0.02);
}

.component-detail {
  position: absolute;
  left: 26px;
  bottom: 26px;
  z-index: 3;
  width: min(500px, calc(44vw - 40px));
  min-height: 68px;
  display: grid;
  grid-template-columns: 42px 1fr auto;
  align-items: center;
  gap: 14px;
  padding: 13px 16px;
}

.component-detail__code {
  color: var(--accent);
  font-size: 11px;
  font-weight: 800;
}

.component-detail h2 {
  font-size: 17px;
  line-height: 1.1;
  margin-bottom: 3px;
}

.component-detail p {
  color: var(--text-dim);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.35;
}

.component-detail__sub {
  margin-top: 2px;
}

.fault-summary {
  display: grid;
  gap: 3px;
}

.component-detail__impact {
  color: var(--positive);
  font-size: 20px;
  white-space: nowrap;
}
```

with:

```css
.component-callout,
.depreciation-panel,
.booking-modal {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  backdrop-filter: blur(12px);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.42), inset 0 0 0 1px rgba(0, 210, 190, 0.02);
}

@keyframes callout-in {
  from {
    opacity: 0;
    margin-top: 8px;
  }
  to {
    opacity: 1;
    margin-top: 0;
  }
}

.component-callout {
  position: absolute;
  z-index: 3;
  width: min(360px, 32vw);
  min-height: 68px;
  display: grid;
  grid-template-columns: 42px 1fr auto;
  align-items: center;
  gap: 14px;
  padding: 13px 16px;
  animation: callout-in 180ms ease-out;
}

.component-callout--top {
  top: 14%;
  left: 50%;
  transform: translateX(-50%);
}

.component-callout--left {
  top: 48%;
  left: 14%;
}

.component-callout--lower-right {
  top: 66%;
  right: 8%;
}

.component-callout__code {
  color: var(--accent);
  font-size: 11px;
  font-weight: 800;
}

.component-callout h2 {
  font-size: 17px;
  line-height: 1.1;
  margin-bottom: 3px;
}

.component-callout p {
  color: var(--text-dim);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.35;
}

.component-callout__sub {
  margin-top: 2px;
}

.fault-summary {
  display: grid;
  gap: 3px;
}

.component-callout__impact {
  color: var(--positive);
  font-size: 20px;
  white-space: nowrap;
}
```

(`.impact-negative` right after stays untouched — it doesn't reference `component-detail`.)

In the `@media (max-width: 1120px)` block, change:

```css
  .stage-topbar,
  .value-header,
    .telemetry-rail,
    .component-dock,
    .car-stage,
    .component-detail,
    .cta-cluster,
  .depreciation-panel,
  .orbit-hint {
```
to:
```css
  .stage-topbar,
  .value-header,
    .telemetry-rail,
    .component-dock,
    .car-stage,
    .component-callout,
    .cta-cluster,
  .depreciation-panel,
  .orbit-hint {
```

Further down in the same media block, change:

```css
  .component-detail {
    grid-template-columns: 42px 1fr;
  }

  .component-detail__impact {
    grid-column: 2;
  }
```
to:
```css
  .component-callout {
    grid-template-columns: 42px 1fr;
  }

  .component-callout__impact {
    grid-column: 2;
  }
```

In the `@media (max-width: 640px)` block, change:

```css
  .component-detail {
    grid-template-columns: 1fr;
  }

  .component-detail__impact {
    grid-column: auto;
  }
```
to:
```css
  .component-callout {
    grid-template-columns: 1fr;
  }

  .component-callout__impact {
    grid-column: auto;
  }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/scene/CarScene.test.ts`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 5: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS — confirms no other test file references the old `.component-detail*` classes.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles/theme.css frontend/src/scene/CarScene.test.ts
git commit -m "feat: anchor component callout card to 3 fixed points around the car"
```

---

### Task 4: Manual verification in the browser

**Files:** none (manual QA pass — no code changes expected; if something looks wrong, fix it in the relevant file from Task 2 or 3 and re-run that task's tests before re-committing)

- [ ] **Step 1: Type-check and build**

Run: `cd frontend && npm run build`
Expected: succeeds (this runs `tsc --noEmit` first, so it also confirms the new `anchor` field and its `"top" | "left" | "lower-right"` union are used consistently across `componentConfig.ts` and `ComponentDetail.tsx`).

- [ ] **Step 2: Start the dev server and open the dashboard**

Run: `cd frontend && npm run dev`
Open the printed local URL in a browser at a desktop width (≥1200px).

- [ ] **Step 3: Click through all 7 dock buttons**

For each of Engine, Battery, Brakes, Fuel, Odometer, Diagnostics, Service in the right-side dock: click it and confirm the callout card appears at the anchor from the mapping table (Engine/Fuel/Service → top-center; Battery/Odometer → left-flank; Brakes/Diagnostics → lower-right), with a visible fade-in, and no overlap with the telemetry rail, dock, CTA buttons, or depreciation chart.

- [ ] **Step 4: Click a highlighted 3D part**

Click one of the glowing regions on the car model directly (e.g. the battery glow box) and confirm it selects the same component and moves the card to the matching anchor, same as clicking its dock button.

- [ ] **Step 5: Resize to a mobile width**

Resize the browser to ≤1120px width (or use device toolbar at e.g. 390px) and confirm the callout card renders as a static, full-width block below the car (like the rest of the stacked layout), not floating at a fixed anchor.

- [ ] **Step 6: No commit for this task**

This task only verifies behavior; only commit here if Step 3, 4, or 5 surfaced a fix to a file from an earlier task (in which case, amend that task's tests if needed and commit the fix on its own, with a message describing what was wrong).

---

## Self-review notes

- **Spec coverage:** Goal 1 (replace fixed card) → Tasks 2–3. Goal 2 (fade between anchors on selection) → Task 2 (`key` + class) and Task 3 (`callout-in` animation). Goal 3 (simple, fixed mapping, no per-part projection) → Task 1. Goal 4 (always one card visible, Engine default) → unchanged `useState<ComponentId>("engine")` in `App.tsx`, not touched by this plan since it already satisfies the requirement. Mobile non-goal → Task 3's media-query renames preserve the existing static-layout override untouched in behavior. Manual verification steps in the spec's "Testing notes" → Task 4.
- **Type consistency:** `anchor: "top" | "left" | "lower-right"` (Task 1) matches the class suffix used in `ComponentDetail.tsx` (Task 2, `component-callout--${component.anchor}`) and the CSS selectors in `theme.css` (Task 3, `.component-callout--top/--left/--lower-right`) and the assertions in `CarScene.test.ts` — same 3 strings used everywhere, no renaming drift.
- **No placeholders:** every step has full, real code — no TODOs or "add appropriate X" phrasing.
