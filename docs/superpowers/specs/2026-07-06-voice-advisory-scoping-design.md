# Voice advisor scoping + audio-reactive visualizer

## Problem

The voice assistant (`VoiceAdvisor`) currently:
- Mounts on the main dashboard (`App.tsx:237`) and auto-starts wake-word listening (`useEffect` at `VoiceAdvisor.tsx:524`, calling `startOneShotRecognition("wake")` at line 633) as soon as the app loads, regardless of whether the user wants voice interaction.
- Renders its "Listening for wake phrase..." pill and a fixed, page-wide debug panel over the whole dashboard at all times.

The user wants voice interaction to only be active when they open the AI Advisory panel, and wants the pill inside that panel to become a real audio-reactive visualizer once the wake phrase is heard, reverting to the pill when listening returns to idle.

## Goals

1. Mic access and wake-word recognition only run while the Advisory modal is open.
2. Alt+A / Alt+D keep working even when the modal is closed, by auto-opening it first.
3. The voice pill/visualizer and the debug panel move from the dashboard into the Advisory modal.
4. Inside the modal, the pill (text + orb) shows while `voiceState === "waiting_for_wake"` (or `"unsupported"`); a 7-bar vertical visualizer shows for every other voice state.
5. Bars are driven by real audio amplitude — live mic input while listening, TTS/filler playback while speaking — with a graceful idle-pulse fallback if the analysis stream can't be acquired.

## Non-goals

- No change to the wake-word matching logic, question-answering flow, backend TTS API, or retry/follow-up timers in `VoiceAdvisor.tsx` — only lifecycle triggers (when recognition starts/stops) and UI presentation change.
- No change to `AdvisoryModal`'s existing advisory content (hero, chart, Gemini insight card, action buttons).
- Not building a generic reusable visualizer component library — just what this feature needs.

## Design

### 1. Lifecycle: modal-scoped mic

`AdvisoryModal` already returns `null` when `!open` (line 44), so `VoiceAdvisor` naturally unmounts when the modal closes and mounts fresh when it opens. Its existing mount/unmount `useEffect` (currently `VoiceAdvisor.tsx:524-660`) already does the right thing once it's only mounted while the modal is open — no `open` prop or open/close branching needed inside `VoiceAdvisor` itself. The mount effect's `startOneShotRecognition("wake")` call now naturally means "start listening when the modal opens", and the cleanup (`stopAllVoice()`, detach handlers, `stopRecognition()`) naturally means "stop when the modal closes."

The Alt+A/Alt+D keyboard effect (currently `VoiceAdvisor.tsx:662-681`, living inside a component that will no longer always be mounted) moves to `App.tsx`, which is always mounted (see below).

### 2. Where keyboard shortcuts live and how they reach VoiceAdvisor

`App.tsx` owns a new `pendingVoiceAction` state: `"greet" | "demo" | null`. Its Alt+A/Alt+D `keydown` listener (moved from `VoiceAdvisor.tsx`) does, for both keys, regardless of whether the modal is currently open or closed:
- `setAdvisoryOpen(true)` (no-op if already open).
- `setPendingVoiceAction("greet")` for Alt+A, `"demo"` for Alt+D.

`pendingVoiceAction` and a `onPendingVoiceActionHandled: () => void` callback (which calls `setPendingVoiceAction(null)`) are passed down through `AdvisoryModal` to `VoiceAdvisor` as props. `VoiceAdvisor` has a `useEffect` on `[pendingVoiceAction]` that, once its recognition object is initialized (i.e. after its mount effect has run), executes `greet()` or `answerQuestion(demoQuestion, {demo:true})` per the value, then calls `onPendingVoiceActionHandled()`.

This sidesteps the mount-timing problem an imperative ref would have: when the modal was just closed, `setAdvisoryOpen(true)` and `setPendingVoiceAction(...)` land in the same render; `VoiceAdvisor` mounts, runs its own setup effect, and then its `pendingVoiceAction` effect fires the action — no ref needed, and no race between "is the child mounted yet" and "is recognition ready yet."

### 3. AdvisoryModal changes

- Renders `<VoiceAdvisor pendingVoiceAction={...} onPendingVoiceActionHandled={...} />` inside the modal body, in a new status-bar row between `.advisory-modal__header` and `.advisory-hero`, forwarding both props straight through from `AdvisoryModalProps`.
- `VoiceAdvisor`'s own top-level markup changes from `position: absolute` (dashboard-specific) to a normal-flow block (`.advisory-voice-bar` wrapper), full width of the modal's content area, keeping the same pill visual styling (border, radius, backdrop-blur, font) from `theme.css:301-321`.
- The response text box (`voice-advisor__response`) and debug panel also move to normal in-flow positioning within the modal instead of `position: fixed`/`position: absolute` tied to the dashboard.

### 4. Pill vs. Visualizer

In `VoiceAdvisor`'s render:
```
const showPill = voiceState === "waiting_for_wake" || voiceState === "unsupported";
```
- `showPill` true → existing pill markup (orb + label + kbd hints).
- `showPill` false → `<VoiceVisualizer level={level} idle={!hasLiveSource} />` in place of the label, inside the same pill-shaped container (so width/height/border don't jump between states).

`VoiceVisualizer` (new small component, colocated in `VoiceAdvisor.tsx` or a new `VoiceVisualizer.tsx`):
- Renders 7 `<span>` bars in a flex row.
- Each bar's height is derived from a smoothed frequency-domain sample (see below) plus a small per-bar phase offset so bars don't move in lockstep.
- Accepts a 0–1 `level` (overall amplitude) and an `idle` flag; when `idle`, bars run a slow CSS `@keyframes` breathing animation instead of reading `level`.

### 5. Audio analysis

New module `frontend/src/components/voiceAudioLevel.ts`:
- `getAudioContext()` — lazily creates/resumes a single shared `AudioContext` (resume happens on Advisory-button click, a user gesture, avoiding autoplay-policy blocks).
- `useMicLevel(active: boolean)` hook — when `active` (i.e. `recognitionState === "listening"` and mode is question/followup), calls `getUserMedia({audio:true})` once, builds `createMediaStreamSource(stream)` → `AnalyserNode`, and polls `getByteFrequencyData` on a `requestAnimationFrame` loop, returning a smoothed 0–1 level. Stops tracks and disconnects on `active` becoming false or unmount. On any `getUserMedia`/`AudioContext` error, returns `{ level: 0, idle: true }` so the caller falls back to the idle pulse.
- `usePlaybackLevel(audioElement: HTMLAudioElement | null)` hook — when a new `<audio>` element starts playing (via `speakAssistant`), creates a `MediaElementAudioSourceNode` for it *once* (source nodes can only be created once per element), connects it through an `AnalyserNode` to `context.destination` (required — otherwise the element goes silent, since routing through Web Audio replaces its default output), and polls the same way.
- `voiceAdvisory.ts`'s `speakAssistant` passes the created `Audio` element out (via a new `onAudioElement` callback) so `VoiceAdvisor` can attach `usePlaybackLevel` to it without `voiceAdvisory.ts` needing to know about visualization.

`VoiceAdvisor` picks whichever level source applies to the current `voiceState`:
- `waiting_for_question` / `waiting_for_followup` → mic level.
- `speaking` / `filler` (when filler audio is actually playing) → playback level.
- `answering` / `generating_voice` (no live audio yet) → idle pulse.

### 6. Debug panel

Moves from a `position: fixed` overlay to a block inside the modal (e.g. below `.advisory-actions` or beside the status bar — visually de-emphasized, small monospace box), only rendered because `VoiceAdvisor` itself only renders while the modal is open. No visibility toggle needed since mount state already gates it.

### 7. Styling

New/updated `theme.css` rules:
- `.advisory-voice-bar` — replaces `.voice-advisor`'s absolute positioning with normal flow, full width, same colors/border/font.
- `.voice-visualizer` — flex row, 7 `span.voice-visualizer__bar` children, `align-items: center; justify-content: center; gap: 3px`, fixed container height matching the pill's height so swapping pill↔visualizer doesn't reflow the modal.
- `.voice-visualizer__bar` — width ~3px, `background: var(--accent)`, `border-radius: 2px`, `transition: height 90ms linear` (or JS-driven inline height set on each animation frame, no CSS transition, to avoid lag behind real amplitude).
- `.voice-visualizer--idle .voice-visualizer__bar` — `@keyframes` gentle breathing loop (staggered `animation-delay` per bar) instead of JS-driven height.

## Data flow summary

```
App.tsx
  advisoryOpen state (unchanged) → AdvisoryModal open prop
  pendingVoiceAction state (new) → AdvisoryModal → VoiceAdvisor prop
  Alt+A/Alt+D listener (moved here) → setAdvisoryOpen(true) + setPendingVoiceAction(...)

AdvisoryModal (open=true)
  → renders VoiceAdvisor (mounts only now), forwarding pendingVoiceAction props
      → mount effect: create SpeechRecognition, startOneShotRecognition("wake")
      → unmount effect (on close): stopAllVoice(), detach handlers, stop mic analyser stream
      → pendingVoiceAction effect: runs greet()/demo question once ready, then clears it
      → renders .advisory-voice-bar: pill OR VoiceVisualizer based on voiceState
      → renders debug panel (in-modal, always-mounted-while-open)
  → renders existing advisory content unchanged
```

## Testing notes

- Manual verification via the dev server: open Advisory modal → confirm mic permission prompt / recognition starts; say "Hey AssetIQ" → pill becomes bars; close modal → confirm recognition and any mic stream stop (no lingering mic indicator).
- Alt+A with modal closed → modal opens and greeting plays.
- Deny mic permission for the analyser stream (or simulate failure) → bars still animate via idle pulse; wake-word matching still works (it uses the separate `SpeechRecognition` API, unaffected).
