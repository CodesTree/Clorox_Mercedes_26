# Floating component cards anchored around the 3D car

## Problem

The dashboard currently shows a single `ComponentDetail` card (`frontend/src/components/ComponentDetail.tsx`) permanently fixed at the bottom-left of the screen (`.component-detail`, `frontend/src/styles/theme.css:615`). It never moves — only its text content swaps when a different component is selected, whether via the side nav dock (`ComponentDock.tsx`) or by clicking the matching highlighted part on the 3D car (`CarScene.tsx`).

The user wants the card to instead feel anchored to the car itself: it should pop up at one of a few fixed points around the model, and switching components should visibly move the card to a different spot rather than just swapping text in place.

## Goals

1. Replace the fixed bottom-left card with a floating "callout" card that always appears at one of 3 fixed screen anchors.
2. Selecting a component (dock button or matching 3D part) fades out the current card and fades in the new component's card at its assigned anchor.
3. Keep the mapping from component to anchor simple and predictable — no per-part screen-projection math.
4. Preserve today's default-selection behavior: exactly one card is always visible (Engine selected on load).

## Non-goals

- No change to `ComponentDetail`'s content/logic (the per-component paragraph, value/sub line, impact figure) — only its positioning and transition.
- No change to `ComponentDock` or `CarScene` selection logic — they already call the same `onSelect(id)` callback this feature reads from.
- No per-part anchor computation (e.g. projecting the clicked 3D part's screen position) — anchors are fixed, not dynamic.
- No new anchor behavior on mobile/narrow layouts (≤1120px) — existing stacked layout is unchanged.

## Design

### 1. The 3 anchors

Three fixed screen positions, placed to avoid the telemetry rail (left), component dock (right), CTA button row (bottom-center), and depreciation chart (bottom-right):

- **top-center** — below the price header (`ValueHeader`), above the car.
- **left-flank** — close to the car's left side, in the gap below the telemetry rail.
- **lower-right** — below the component dock, right-of-center, in the gap just above the depreciation chart.

### 2. Component → anchor mapping

Each component gets a fixed anchor, computed from its existing position in the `COMPONENTS` array (`componentConfig.ts`) via `index % 3`. This is added as an explicit `anchor` field on each entry (not computed at render time) so the mapping is visible and editable in one place:

| Component | Index | Anchor |
|---|---|---|
| Engine | 0 | top-center |
| Battery | 1 | left-flank |
| Brakes | 2 | lower-right |
| Fuel | 3 | top-center |
| Odometer | 4 | left-flank |
| Diagnostics | 5 | lower-right |
| Service | 6 | top-center |

`ComponentItem` gains: `anchor: "top" | "left" | "lower-right"`.

### 3. Rendering and transition

`ComponentDetail` keeps its existing props and internal per-component content branches unchanged. Only its wrapping class changes:

```
<section className={`component-callout component-callout--${component.anchor}`} key={component.id} ...>
```

The `key={component.id}` forces React to unmount/remount the card on selection change, which combined with a CSS enter animation gives a clean fade-in at the new anchor without needing to track "old" vs "new" card state or animate between two positions. A plain CSS `@keyframes` fade + slight upward slide (~180ms, ease-out) runs on mount, matching the app's existing ~160ms-ease motion elsewhere (`theme.css:1183`). No exit animation is needed since the old card is removed synchronously when the new one mounts at a different fixed spot — there is no shared position to tween between.

### 4. Styling

In `theme.css`, replace the single `.component-detail` absolute-position rule (`theme.css:615-627`) with:

- `.component-callout` — shared card styling (border/background/blur/shadow, same as today's `.component-detail`/`.depreciation-panel`/`.booking-modal` shared rule at `theme.css:605`), plus the fade-in keyframe animation. Width narrows from today's `min(500px, calc(44vw - 40px))` to roughly `min(360px, 32vw)` so it fits each anchor's gap without overlapping neighboring fixed panels.
- `.component-callout--top` — positioned top-center, below `ValueHeader`.
- `.component-callout--left` — positioned left-flank, close to the car.
- `.component-callout--lower-right` — positioned lower-right, below the dock and above the depreciation chart.

Internal layout (code / heading+text / impact figure grid) is unchanged from today's `.component-detail` rules — only the outer positioning rules are replaced.

### 5. Mobile (≤1120px)

Unchanged. The existing breakpoint (`theme.css:1707-1802`) already overrides `.component-detail` (→ `.component-callout`) to `position: static`, full width, stacked in normal flow below the car. Since all three `--top`/`--left`/`--lower-right` variants only set `position: absolute` + coordinates, the existing static override at the breakpoint applies uniformly regardless of which anchor variant is active, with no extra rules needed.

## Testing notes

- Update `ComponentDetail`'s existing render test(s) to assert the correct `component-callout--*` class is applied for a representative component from each anchor group (e.g. Engine → top, Battery → left, Brakes → lower-right).
- Manual check via dev server at desktop width: click through all 7 dock buttons and confirm the card appears at the expected anchor each time with no overlap against telemetry rail, dock, CTA row, or depreciation chart; click a highlighted 3D part and confirm the same.
- Manual check at ≤1120px width: confirm the card still renders as a static full-width block below the car, matching current mobile behavior.
