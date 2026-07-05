# Voice Advisor Scoping + Audio-Reactive Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scope the voice assistant's mic/wake-word listening to only run while the AI Advisory modal is open, and replace its "listening" pill with a real audio-reactive bar visualizer once the wake phrase is heard, reverting to the pill when listening idles back to waiting-for-wake.

**Architecture:** Extract pure, unit-testable logic (pill-vs-visualizer state mapping, level-source selection, bar-height math, byte-array-to-level math) into small standalone modules. Layer browser-API-touching hooks (`useMicLevel`, `usePlaybackLevel`, shared `AudioContext`) on top in their own module, tested with mocked Web Audio/`getUserMedia` globals. Wire it all into the existing `VoiceAdvisor` component, move it (and its debug panel) into `AdvisoryModal`, and move the Alt+A/Alt+D keyboard shortcut up into `App.tsx` since it must keep working while the modal — and therefore `VoiceAdvisor` — is unmounted.

**Tech Stack:** React 18 + TypeScript, Vite, Vitest + @testing-library/react + jsdom (existing project stack; no new dependencies).

**Spec:** `docs/superpowers/specs/2026-07-06-voice-advisory-scoping-design.md`

**Testing scope note:** This codebase has zero existing frontend tests despite vitest/testing-library being installed. This plan adds focused unit tests for every new pure function and hook (cheap, deterministic, high value), plus one lean integration test per modified component covering its new behavioral contract. It does not retroactively write exhaustive tests for pre-existing untested logic in `VoiceAdvisor.tsx`/`voiceAdvisory.ts` that this change doesn't touch. The final task is manual verification in a real browser, per this project's convention for UI changes.

---

## File map

- Create `frontend/src/components/voiceVisualizerLogic.ts` + `.test.ts` — pure functions: `isPillState`, `levelSourceForState`, `barHeightPx`.
- Create `frontend/src/components/VoiceVisualizer.tsx` + `.test.tsx` — the 7-bar visualizer component.
- Create `frontend/src/components/voiceAudioLevel.ts` + `.test.ts` — `levelFromFrequencyData`, `getAudioContext`, `useMicLevel`, `usePlaybackLevel`.
- Modify `frontend/src/components/voiceAdvisory.ts` — add `onAudioElement` callback to `speakAssistant`.
- Create `frontend/src/components/voiceAdvisory.test.ts` — test the new callback only.
- Modify `frontend/src/components/VoiceAdvisor.tsx` — accept `pendingVoiceAction`/`onPendingVoiceActionHandled` props, remove its own keyboard effect, swap pill/visualizer, wire level hooks.
- Create `frontend/src/components/VoiceAdvisor.test.tsx` — pill↔visualizer swap + pending-action handling.
- Modify `frontend/src/components/AdvisoryModal.tsx` — render `VoiceAdvisor` inside the modal, forward new props.
- Create `frontend/src/components/AdvisoryModal.test.tsx` — prop forwarding + open/closed rendering.
- Modify `frontend/src/App.tsx` — own `pendingVoiceAction` state, move the Alt+A/Alt+D listener here, stop rendering `VoiceAdvisor` on the dashboard.
- Create `frontend/src/App.test.tsx` — Alt+A with modal closed opens it.
- Modify `frontend/src/styles/theme.css` — new visualizer/status-bar styles, remove now-dead dashboard-specific `.voice-advisor` positioning rules.

---

### Task 1: Pure visualizer logic (`voiceVisualizerLogic.ts`)

**Files:**
- Create: `frontend/src/components/voiceVisualizerLogic.ts`
- Test: `frontend/src/components/voiceVisualizerLogic.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/components/voiceVisualizerLogic.test.ts
import { describe, expect, it } from "vitest";
import { barHeightPx, isPillState, levelSourceForState } from "./voiceVisualizerLogic";

describe("isPillState", () => {
  it("is true for waiting_for_wake and unsupported", () => {
    expect(isPillState("waiting_for_wake")).toBe(true);
    expect(isPillState("unsupported")).toBe(true);
  });

  it("is false for every other voice state", () => {
    const activeStates = [
      "greeting",
      "waiting_for_question",
      "waiting_for_followup",
      "filler",
      "answering",
      "generating_voice",
      "speaking",
      "text_only",
      "playback_error",
    ] as const;
    for (const state of activeStates) {
      expect(isPillState(state)).toBe(false);
    }
  });
});

describe("levelSourceForState", () => {
  it("routes listening states to mic", () => {
    expect(levelSourceForState("waiting_for_question")).toBe("mic");
    expect(levelSourceForState("waiting_for_followup")).toBe("mic");
  });

  it("routes audio-playback states to playback", () => {
    expect(levelSourceForState("speaking")).toBe("playback");
    expect(levelSourceForState("filler")).toBe("playback");
  });

  it("routes everything else to idle", () => {
    const idleStates = [
      "waiting_for_wake",
      "unsupported",
      "greeting",
      "answering",
      "generating_voice",
      "text_only",
      "playback_error",
    ] as const;
    for (const state of idleStates) {
      expect(levelSourceForState(state)).toBe("idle");
    }
  });
});

describe("barHeightPx", () => {
  it("returns the minimum height for every bar at level 0", () => {
    for (let index = 0; index < 7; index += 1) {
      expect(barHeightPx(0, index, 7)).toBe(6);
    }
  });

  it("returns the tallest bar at the center index for level 1", () => {
    expect(barHeightPx(1, 3, 7)).toBe(28);
  });

  it("returns a shorter bar at the edges than at the center for level 1", () => {
    expect(barHeightPx(1, 0, 7)).toBe(20);
    expect(barHeightPx(1, 6, 7)).toBe(20);
  });

  it("clamps out-of-range level input", () => {
    expect(barHeightPx(-1, 3, 7)).toBe(6);
    expect(barHeightPx(2, 3, 7)).toBe(28);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/voiceVisualizerLogic.test.ts`
Expected: FAIL — `Cannot find module './voiceVisualizerLogic'` (file doesn't exist yet).

- [ ] **Step 3: Write the implementation**

```ts
// frontend/src/components/voiceVisualizerLogic.ts
type VoiceState =
  | "unsupported"
  | "waiting_for_wake"
  | "greeting"
  | "waiting_for_question"
  | "waiting_for_followup"
  | "filler"
  | "answering"
  | "generating_voice"
  | "speaking"
  | "text_only"
  | "playback_error";

export type VoiceLevelSource = "mic" | "playback" | "idle";

export function isPillState(voiceState: VoiceState): boolean {
  return voiceState === "waiting_for_wake" || voiceState === "unsupported";
}

export function levelSourceForState(voiceState: VoiceState): VoiceLevelSource {
  if (voiceState === "waiting_for_question" || voiceState === "waiting_for_followup") {
    return "mic";
  }
  if (voiceState === "speaking" || voiceState === "filler") {
    return "playback";
  }
  return "idle";
}

const MIN_BAR_HEIGHT_PX = 6;
const MAX_BAR_HEIGHT_PX = 28;
const EDGE_HEIGHT_FALLOFF = 0.35;

export function barHeightPx(level: number, barIndex: number, barCount: number): number {
  const clampedLevel = Math.max(0, Math.min(1, level));
  const centerOffset = (barCount - 1) / 2 || 1;
  const distanceFromCenter = Math.abs(barIndex - (barCount - 1) / 2) / centerOffset;
  const centerBoost = 1 - distanceFromCenter * EDGE_HEIGHT_FALLOFF;
  const range = MAX_BAR_HEIGHT_PX - MIN_BAR_HEIGHT_PX;
  return Math.round(MIN_BAR_HEIGHT_PX + clampedLevel * centerBoost * range);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/voiceVisualizerLogic.test.ts`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/voiceVisualizerLogic.ts frontend/src/components/voiceVisualizerLogic.test.ts
git commit -m "$(cat <<'EOF'
Add pure voice-visualizer state/level/bar-height logic

Isolates the pill-vs-visualizer and audio-source-selection rules from
the AudioContext/SpeechRecognition plumbing so they're directly
unit-testable.
EOF
)"
```

---

### Task 2: `VoiceVisualizer` component

**Files:**
- Create: `frontend/src/components/VoiceVisualizer.tsx`
- Test: `frontend/src/components/VoiceVisualizer.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/VoiceVisualizer.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VoiceVisualizer } from "./VoiceVisualizer";

describe("VoiceVisualizer", () => {
  it("renders 7 bars", () => {
    render(<VoiceVisualizer level={0.5} idle={false} />);
    const container = screen.getByTestId("voice-visualizer");
    expect(container.querySelectorAll(".voice-visualizer__bar")).toHaveLength(7);
  });

  it("sets bar heights from the level prop when not idle", () => {
    render(<VoiceVisualizer level={1} idle={false} />);
    const bars = screen.getByTestId("voice-visualizer").querySelectorAll<HTMLSpanElement>(".voice-visualizer__bar");
    expect(bars[3].style.height).toBe("28px");
    expect(bars[0].style.height).toBe("20px");
  });

  it("adds the idle modifier class and skips inline heights when idle", () => {
    render(<VoiceVisualizer level={0.8} idle />);
    const container = screen.getByTestId("voice-visualizer");
    expect(container.className).toContain("voice-visualizer--idle");
    const bars = container.querySelectorAll<HTMLSpanElement>(".voice-visualizer__bar");
    expect(bars[0].style.height).toBe("");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/VoiceVisualizer.test.tsx`
Expected: FAIL — `Cannot find module './VoiceVisualizer'`

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/components/VoiceVisualizer.tsx
import { barHeightPx } from "./voiceVisualizerLogic";

interface VoiceVisualizerProps {
  level: number;
  idle: boolean;
}

const BAR_COUNT = 7;

export function VoiceVisualizer({ level, idle }: VoiceVisualizerProps) {
  return (
    <div
      className={`voice-visualizer${idle ? " voice-visualizer--idle" : ""}`}
      data-testid="voice-visualizer"
      aria-hidden="true"
    >
      {Array.from({ length: BAR_COUNT }, (_, index) => (
        <span
          key={index}
          className="voice-visualizer__bar"
          style={idle ? undefined : { height: `${barHeightPx(level, index, BAR_COUNT)}px` }}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/VoiceVisualizer.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/VoiceVisualizer.tsx frontend/src/components/VoiceVisualizer.test.tsx
git commit -m "$(cat <<'EOF'
Add VoiceVisualizer bar component

Renders the 7-bar amplitude display that replaces the wake-phrase pill
once voice interaction is active.
EOF
)"
```

---

### Task 3: Audio level hooks (`voiceAudioLevel.ts`)

**Files:**
- Create: `frontend/src/components/voiceAudioLevel.ts`
- Test: `frontend/src/components/voiceAudioLevel.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/components/voiceAudioLevel.test.ts
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

class FakeAnalyserNode {
  fftSize = 256;
  frequencyBinCount = 128;
  constructor(private readonly data: Uint8Array) {}
  getByteFrequencyData(array: Uint8Array) {
    array.set(this.data.subarray(0, array.length));
  }
}

function makeFakeContext(analyserData: Uint8Array) {
  const analyser = new FakeAnalyserNode(analyserData);
  return {
    createAnalyser: vi.fn(() => analyser),
    createMediaStreamSource: vi.fn(() => ({ connect: vi.fn(), disconnect: vi.fn() })),
    createMediaElementSource: vi.fn(() => ({ connect: vi.fn(), disconnect: vi.fn() })),
    destination: {},
  };
}

describe("voiceAudioLevel", () => {
  let rafCallback: FrameRequestCallback | null;

  beforeEach(() => {
    vi.resetModules();
    rafCallback = null;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      rafCallback = cb;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("levelFromFrequencyData averages byte values into a 0-1 range", async () => {
    const { levelFromFrequencyData } = await import("./voiceAudioLevel");
    expect(levelFromFrequencyData(new Uint8Array([0, 0]))).toBe(0);
    expect(levelFromFrequencyData(new Uint8Array([128, 128]))).toBe(1);
    expect(levelFromFrequencyData(new Uint8Array([64, 64]))).toBeCloseTo(0.5, 5);
  });

  it("useMicLevel stays idle when getUserMedia is unavailable", async () => {
    vi.stubGlobal("navigator", { mediaDevices: undefined });
    vi.stubGlobal("AudioContext", vi.fn(() => makeFakeContext(new Uint8Array([0]))));
    const { useMicLevel } = await import("./voiceAudioLevel");

    const { result } = renderHook(() => useMicLevel(true));
    expect(result.current).toEqual({ level: 0, idle: true });
  });

  it("useMicLevel reads a level from the analyser once the stream resolves, and stops the stream on cleanup", async () => {
    const stopTrack = vi.fn();
    const fakeStream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
    });
    vi.stubGlobal("AudioContext", vi.fn(() => makeFakeContext(new Uint8Array([128, 128]))));
    const { useMicLevel } = await import("./voiceAudioLevel");

    const { result, unmount } = renderHook(() => useMicLevel(true));
    await waitFor(() => expect(result.current.idle).toBe(false));
    act(() => rafCallback?.(0));
    expect(result.current.level).toBe(1);

    unmount();
    expect(stopTrack).toHaveBeenCalled();
  });

  it("usePlaybackLevel reads a level from the provided audio element", async () => {
    vi.stubGlobal("AudioContext", vi.fn(() => makeFakeContext(new Uint8Array([64, 64]))));
    const { usePlaybackLevel } = await import("./voiceAudioLevel");
    const audio = new Audio();

    const { result } = renderHook(() => usePlaybackLevel(audio));
    expect(result.current.idle).toBe(false);
    act(() => rafCallback?.(0));
    expect(result.current.level).toBeCloseTo(0.5, 5);
  });

  it("usePlaybackLevel is idle when there is no audio element", async () => {
    vi.stubGlobal("AudioContext", vi.fn(() => makeFakeContext(new Uint8Array([0]))));
    const { usePlaybackLevel } = await import("./voiceAudioLevel");

    const { result } = renderHook(() => usePlaybackLevel(null));
    expect(result.current).toEqual({ level: 0, idle: true });
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/voiceAudioLevel.test.ts`
Expected: FAIL — `Cannot find module './voiceAudioLevel'`

- [ ] **Step 3: Write the implementation**

```ts
// frontend/src/components/voiceAudioLevel.ts
import { useEffect, useRef, useState } from "react";

export function levelFromFrequencyData(data: Uint8Array): number {
  if (data.length === 0) return 0;
  let sum = 0;
  for (let index = 0; index < data.length; index += 1) {
    sum += data[index];
  }
  return Math.min(1, sum / data.length / 128);
}

let sharedAudioContext: AudioContext | null = null;

export function getAudioContext(): AudioContext | null {
  if (sharedAudioContext) return sharedAudioContext;
  const Ctor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  sharedAudioContext = new Ctor();
  return sharedAudioContext;
}

interface LevelResult {
  level: number;
  idle: boolean;
}

function pollAnalyser(analyser: AnalyserNode, onLevel: (level: number) => void): () => void {
  const data = new Uint8Array(analyser.frequencyBinCount);
  let frameId = 0;
  let cancelled = false;

  const tick = () => {
    if (cancelled) return;
    analyser.getByteFrequencyData(data);
    onLevel(levelFromFrequencyData(data));
    frameId = window.requestAnimationFrame(tick);
  };
  frameId = window.requestAnimationFrame(tick);

  return () => {
    cancelled = true;
    window.cancelAnimationFrame(frameId);
  };
}

export function useMicLevel(active: boolean): LevelResult {
  const [level, setLevel] = useState(0);
  const [idle, setIdle] = useState(true);

  useEffect(() => {
    if (!active) {
      setLevel(0);
      setIdle(true);
      return undefined;
    }

    let cancelled = false;
    let stopPolling: (() => void) | null = null;
    let stream: MediaStream | null = null;

    const context = getAudioContext();
    if (!context || !navigator.mediaDevices?.getUserMedia) {
      setIdle(true);
      return undefined;
    }

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((acquiredStream) => {
        if (cancelled) {
          acquiredStream.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = acquiredStream;
        const source = context.createMediaStreamSource(acquiredStream);
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        setIdle(false);
        stopPolling = pollAnalyser(analyser, setLevel);
      })
      .catch(() => {
        setIdle(true);
      });

    return () => {
      cancelled = true;
      stopPolling?.();
      stream?.getTracks().forEach((track) => track.stop());
      setIdle(true);
      setLevel(0);
    };
  }, [active]);

  return { level, idle };
}

export function usePlaybackLevel(audioElement: HTMLAudioElement | null): LevelResult {
  const [level, setLevel] = useState(0);
  const [idle, setIdle] = useState(true);
  const sourceCacheRef = useRef(new WeakMap<HTMLAudioElement, MediaElementAudioSourceNode>());

  useEffect(() => {
    if (!audioElement) {
      setLevel(0);
      setIdle(true);
      return undefined;
    }

    const context = getAudioContext();
    if (!context) {
      setIdle(true);
      return undefined;
    }

    let source = sourceCacheRef.current.get(audioElement);
    if (!source) {
      source = context.createMediaElementSource(audioElement);
      source.connect(context.destination);
      sourceCacheRef.current.set(audioElement, source);
    }

    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    setIdle(false);
    const stopPolling = pollAnalyser(analyser, setLevel);

    return () => {
      stopPolling();
      setIdle(true);
      setLevel(0);
    };
  }, [audioElement]);

  return { level, idle };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/voiceAudioLevel.test.ts`
Expected: PASS (5 tests). If a test fails on jsdom-specific global behavior (e.g. `navigator` stubbing), inspect the failure output and adjust the stub — do not weaken the assertions.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/voiceAudioLevel.ts frontend/src/components/voiceAudioLevel.test.ts
git commit -m "$(cat <<'EOF'
Add real audio-reactive level hooks for mic input and TTS playback

useMicLevel polls a dedicated getUserMedia stream (separate from
SpeechRecognition, which doesn't expose levels); usePlaybackLevel taps
the TTS/filler <audio> element via a MediaElementAudioSourceNode. Both
report idle:true on any acquisition failure so callers can fall back
to a non-reactive animation instead of freezing.
EOF
)"
```

---

### Task 4: Expose the playback `Audio` element from `speakAssistant`

**Files:**
- Modify: `frontend/src/components/voiceAdvisory.ts:58-65,159-214`
- Test: `frontend/src/components/voiceAdvisory.test.ts` (new)

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/components/voiceAdvisory.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { speakAssistant, stopAllVoice } from "./voiceAdvisory";

describe("speakAssistant onAudioElement", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:mock"), revokeObjectURL: vi.fn() });
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  afterEach(() => {
    stopAllVoice();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("passes the created Audio element to onAudioElement before playback starts", () => {
    let receivedElement: HTMLAudioElement | null = null;
    const didStart = speakAssistant({
      text: "hello",
      audioBase64: btoa("fake-audio-bytes"),
      mimeType: "audio/wav",
      onStart: () => undefined,
      onEnd: () => undefined,
      onPlaybackError: () => undefined,
      onAudioElement: (element) => {
        receivedElement = element;
      },
    });

    expect(didStart).toBe(true);
    expect(receivedElement).toBeInstanceOf(HTMLAudioElement);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/voiceAdvisory.test.ts`
Expected: FAIL — TypeScript error / test failure because `onAudioElement` isn't a recognized option and is never called (`receivedElement` stays `null`).

- [ ] **Step 3: Modify the implementation**

In `frontend/src/components/voiceAdvisory.ts`, update the options interface (currently lines 58-65):

```ts
interface SpeakAssistantOptions {
  text: string;
  audioBase64?: string | null;
  mimeType?: string | null;
  onStart: () => void;
  onEnd: () => void;
  onPlaybackError: (error: unknown) => void;
  onAudioElement?: (audio: HTMLAudioElement) => void;
}
```

Update `speakAssistant`'s signature and body (currently lines 159-214) to destructure and call the new callback right after the `Audio` instance is created:

```ts
export function speakAssistant({
  audioBase64,
  mimeType,
  onStart,
  onEnd,
  onPlaybackError,
  onAudioElement,
}: SpeakAssistantOptions) {
  if (isSpeaking) return false;
  if (!audioBase64) return false;

  stopAllVoice();

  let finished = false;
  const fail = (error: unknown) => {
    if (finished) return;
    finished = true;
    isSpeaking = false;
    currentAudio = null;
    onPlaybackError(error);
  };

  isSpeaking = true;
  onStart();

  const finish = () => {
    if (finished) return;
    finished = true;
    isSpeaking = false;
    currentAudio = null;
    onEnd();
  };

  let url: string | null = null;
  try {
    console.log("[voice] playback path: gemini-audio");
    url = base64ToBlobUrl(audioBase64, mimeType || "audio/wav");
    const audio = new Audio(url);
    currentAudio = audio;
    onAudioElement?.(audio);
    audio.onended = () => {
      console.log("[voice] gemini audio ended");
      if (url) URL.revokeObjectURL(url);
      currentAudio = null;
      finish();
    };
    audio.onerror = (error) => {
      console.warn("[voice] Gemini audio playback failed", error);
      if (url) URL.revokeObjectURL(url);
      fail(error);
    };
    audio.play().catch((error) => {
      console.warn("[voice] Gemini audio play() rejected", error);
      if (url) URL.revokeObjectURL(url);
      fail(error);
    });
    return true;
  } catch (error) {
    console.warn("[voice] Failed to decode Gemini audio", error);
    if (url) URL.revokeObjectURL(url);
    fail(error);
    return true;
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/voiceAdvisory.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/voiceAdvisory.ts frontend/src/components/voiceAdvisory.test.ts
git commit -m "$(cat <<'EOF'
Expose the TTS Audio element via speakAssistant's onAudioElement

Lets callers (VoiceAdvisor) attach a Web Audio analyser to the actual
playback element for the audio-reactive visualizer, without
voiceAdvisory.ts needing to know anything about visualization.
EOF
)"
```

---

### Task 5: Wire `VoiceAdvisor` to the new pill/visualizer + pending-action props

**Files:**
- Modify: `frontend/src/components/VoiceAdvisor.tsx`
- Test: `frontend/src/components/VoiceAdvisor.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/VoiceAdvisor.test.tsx
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import { VoiceAdvisor } from "./VoiceAdvisor";

vi.mock("./voiceAudioLevel", () => ({
  useMicLevel: () => ({ level: 0.4, idle: false }),
  usePlaybackLevel: () => ({ level: 0.4, idle: false }),
}));

class FakeSpeechRecognition {
  static instances: FakeSpeechRecognition[] = [];
  continuous = false;
  interimResults = false;
  lang = "en-US";
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: { error?: string }) => void) | null = null;
  onresult: ((event: unknown) => void) | null = null;
  start = vi.fn(() => this.onstart?.());
  stop = vi.fn(() => this.onend?.());

  constructor() {
    FakeSpeechRecognition.instances.push(this);
  }
}

function makeResultEvent(transcript: string) {
  const item = { transcript };
  const result = { length: 1, isFinal: true, item: () => item, 0: item };
  return { results: { length: 1, item: () => result, 0: result }, resultIndex: 0 };
}

describe("VoiceAdvisor", () => {
  beforeEach(() => {
    FakeSpeechRecognition.instances = [];
    vi.stubGlobal("SpeechRecognition", FakeSpeechRecognition);
    vi.spyOn(client, "respondToAdvisoryVoice").mockResolvedValue({
      reply: "Hi there",
      audio_base64: null,
      mime_type: null,
      tts_provider: "gemini-unavailable",
      fallback_reason: "test",
      text_provider: "local",
      tts_wait_ms: 0,
      gemini_key_detected: false,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the pill while waiting for the wake phrase", () => {
    render(<VoiceAdvisor pendingVoiceAction={null} onPendingVoiceActionHandled={() => undefined} />);
    expect(screen.getByTestId("voice-advisor")).toHaveTextContent("Listening for wake phrase");
    expect(screen.queryByTestId("voice-visualizer")).not.toBeInTheDocument();
  });

  it("swaps to the visualizer once the wake phrase is heard", async () => {
    render(<VoiceAdvisor pendingVoiceAction={null} onPendingVoiceActionHandled={() => undefined} />);
    const recognition = FakeSpeechRecognition.instances[0];

    act(() => {
      recognition.onresult?.(makeResultEvent("hey assetiq"));
    });

    await waitFor(() => expect(screen.getByTestId("voice-visualizer")).toBeInTheDocument());
  });

  it("runs the pending greet action once and reports it handled", async () => {
    const onHandled = vi.fn();
    render(<VoiceAdvisor pendingVoiceAction="greet" onPendingVoiceActionHandled={onHandled} />);

    await waitFor(() => expect(client.respondToAdvisoryVoice).toHaveBeenCalled());
    expect(onHandled).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/VoiceAdvisor.test.tsx`
Expected: FAIL — `VoiceAdvisor` doesn't accept props yet (type error) and the pending-action effect doesn't exist.

- [ ] **Step 3: Modify the implementation**

In `frontend/src/components/VoiceAdvisor.tsx`:

1. Add imports at the top (after the existing `voiceAdvisory` import block):

```ts
import { VoiceVisualizer } from "./VoiceVisualizer";
import { isPillState, levelSourceForState } from "./voiceVisualizerLogic";
import { useMicLevel, usePlaybackLevel } from "./voiceAudioLevel";
```

2. Change the component signature (line 92) from `export function VoiceAdvisor() {` to:

```ts
interface VoiceAdvisorProps {
  pendingVoiceAction: "greet" | "demo" | null;
  onPendingVoiceActionHandled: () => void;
}

export function VoiceAdvisor({ pendingVoiceAction, onPendingVoiceActionHandled }: VoiceAdvisorProps) {
```

3. Add an `activeAudioElement` state near the other `useState` declarations (after line 111's `voiceStatusMessage` state):

```ts
  const [activeAudioElement, setActiveAudioElement] = useState<HTMLAudioElement | null>(null);
```

4. In `playFiller` (the cached-audio branch, currently the `speakAssistant` call inside the `return new Promise<void>((resolve) => { ... })` block around lines 324-339), add `onAudioElement: setActiveAudioElement,` alongside the existing `onStart`/`onEnd`/`onPlaybackError` options:

```ts
      const didStart = speakAssistant({
        text: fillerText,
        audioBase64: cachedFiller.audio_base64,
        mimeType: cachedFiller.mime_type,
        onStart: () => undefined,
        onAudioElement: setActiveAudioElement,
        onEnd: () => {
          console.log("[voice] filler ended");
          setActiveAudioElement(null);
          resolve();
        },
        onPlaybackError: (error) => {
          console.warn("[voice] filler playback failed", error);
          console.log("[voice] filler ended");
          setActiveAudioElement(null);
          resolve();
        },
      });
```

5. In `speakResponse` (currently lines 381-388), add the same callback and clear it in `onSpeechEnd`:

```ts
    const didStart = speakAssistant({
      text,
      audioBase64: response.audio_base64,
      mimeType: response.mime_type,
      onStart: () => onSpeechStart({ answer: options.answer }),
      onAudioElement: setActiveAudioElement,
      onEnd: () => onSpeechEnd(onEnd),
      onPlaybackError: (error) => handlePlaybackError(error, onEnd),
    });
```

6. In `onSpeechEnd` (currently lines 245-249), clear the active element:

```ts
  const onSpeechEnd = (onEnd?: () => void) => {
    speechReservedRef.current = false;
    isSpeakingRef.current = false;
    setActiveAudioElement(null);
    onEnd?.();
  };
```

7. Replace the Alt+A/Alt+D keyboard `useEffect` (currently lines 662-681) — delete it entirely; that responsibility moves to `App.tsx` in Task 7.

8. Add a new effect immediately after the mount effect (which ends at line 660), so it runs after `recognitionRef.current` is guaranteed to be set on first mount:

```ts
  useEffect(() => {
    if (!pendingVoiceAction) return;
    if (speechReservedRef.current || isSpeakingRef.current || getIsSpeaking()) return;

    if (pendingVoiceAction === "greet") {
      stopRecognition();
      greet();
    } else {
      answerQuestion(demoQuestion, { demo: true });
    }
    onPendingVoiceActionHandled();
  }, [pendingVoiceAction]);
```

9. Add level-source wiring just before the `label` computation (currently starting at line 683):

```ts
  const levelSource = levelSourceForState(voiceState);
  const micLevel = useMicLevel(levelSource === "mic");
  const playbackLevel = usePlaybackLevel(levelSource === "playback" ? activeAudioElement : null);
  const { level, idle } =
    levelSource === "mic" ? micLevel : levelSource === "playback" ? playbackLevel : { level: 0, idle: true };
```

10. Replace the pill markup in the render (currently lines 704-711):

```tsx
      <div className={`voice-advisor voice-advisor--${voiceState}`} aria-live="polite" data-testid="voice-advisor">
        {isPillState(voiceState) ? (
          <>
            <span className="voice-advisor__orb" aria-hidden="true" />
            <span>{label}</span>
            <kbd>Alt+A</kbd>
            <kbd>Alt+D</kbd>
          </>
        ) : (
          <VoiceVisualizer level={level} idle={idle} />
        )}
      </div>
```

11. Replace the debug panel's inline-styled `<div>` (currently lines 718-732, the `style={{ position: "fixed", ... }}` block) with a class-based wrapper — remove the `style={{...}}` object and change the opening tag to:

```tsx
      <div className="voice-advisor__debug">
```

(The CSS for `.voice-advisor__debug` is added in Task 8; leave the rest of the debug panel's inner JSX, lines 733-755, unchanged.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/VoiceAdvisor.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full frontend test suite to check for regressions**

Run: `cd frontend && npx vitest run`
Expected: PASS for all suites written so far (Tasks 1-5).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/VoiceAdvisor.tsx frontend/src/components/VoiceAdvisor.test.tsx
git commit -m "$(cat <<'EOF'
Swap VoiceAdvisor's pill for an audio-reactive visualizer post-wake

Renders the pill only in waiting_for_wake/unsupported states and the
VoiceVisualizer everywhere else, driven by mic or TTS playback level
depending on voiceState. Alt+A/Alt+D handling moves out to a
pendingVoiceAction prop so the parent (App.tsx) can trigger it even
before VoiceAdvisor is mounted.
EOF
)"
```

---

### Task 6: Move `VoiceAdvisor` into `AdvisoryModal`

**Files:**
- Modify: `frontend/src/components/AdvisoryModal.tsx`
- Test: `frontend/src/components/AdvisoryModal.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/AdvisoryModal.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdvisoryModal } from "./AdvisoryModal";

vi.mock("./VoiceAdvisor", () => ({
  VoiceAdvisor: ({ pendingVoiceAction }: { pendingVoiceAction: string | null }) => (
    <div data-testid="voice-advisor-stub">{pendingVoiceAction ?? "none"}</div>
  ),
}));

describe("AdvisoryModal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <AdvisoryModal
        open={false}
        profile={null}
        prediction={null}
        depreciation={null}
        snapshot={null}
        faults={[]}
        market={null}
        pendingVoiceAction={null}
        onPendingVoiceActionHandled={() => undefined}
        onClose={() => undefined}
        onBookInspection={() => undefined}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders VoiceAdvisor with the forwarded pending action when open", () => {
    render(
      <AdvisoryModal
        open
        profile={null}
        prediction={null}
        depreciation={null}
        snapshot={null}
        faults={[]}
        market={null}
        pendingVoiceAction="demo"
        onPendingVoiceActionHandled={() => undefined}
        onClose={() => undefined}
        onBookInspection={() => undefined}
      />,
    );
    expect(screen.getByTestId("voice-advisor-stub")).toHaveTextContent("demo");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/AdvisoryModal.test.tsx`
Expected: FAIL — `AdvisoryModal` doesn't accept `pendingVoiceAction`/`onPendingVoiceActionHandled` props, and doesn't render `VoiceAdvisor`.

- [ ] **Step 3: Modify the implementation**

In `frontend/src/components/AdvisoryModal.tsx`:

1. Add the import (after the existing `format` import, line 9):

```ts
import { VoiceAdvisor } from "./VoiceAdvisor";
```

2. Extend `AdvisoryModalProps` (currently lines 11-21):

```ts
interface AdvisoryModalProps {
  open: boolean;
  profile: VehicleProfile | null;
  prediction: PredictOut | null;
  depreciation: DepreciationPoint[] | null;
  snapshot: ObdSnapshotOut | null;
  faults: FaultOut[];
  market: MarketCompsOut | null;
  pendingVoiceAction: "greet" | "demo" | null;
  onPendingVoiceActionHandled: () => void;
  onClose: () => void;
  onBookInspection: () => void;
}
```

3. Destructure the two new props in the function signature (currently lines 33-43):

```ts
export function AdvisoryModal({
  open,
  profile,
  prediction,
  depreciation,
  snapshot,
  faults,
  market,
  pendingVoiceAction,
  onPendingVoiceActionHandled,
  onClose,
  onBookInspection,
}: AdvisoryModalProps) {
```

4. Render `VoiceAdvisor` right after `.advisory-modal__header` and before `.advisory-hero` (currently between lines 79 and 81):

```tsx
        </div>

        <VoiceAdvisor pendingVoiceAction={pendingVoiceAction} onPendingVoiceActionHandled={onPendingVoiceActionHandled} />

        <div className="advisory-hero">
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/AdvisoryModal.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AdvisoryModal.tsx frontend/src/components/AdvisoryModal.test.tsx
git commit -m "$(cat <<'EOF'
Render VoiceAdvisor inside AdvisoryModal

VoiceAdvisor now mounts/unmounts with the modal itself, so mic access
and wake-word listening only run while the Advisory panel is open.
EOF
)"
```

---

### Task 7: Move the keyboard shortcut and stop rendering `VoiceAdvisor` on the dashboard

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/App.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./components/VoiceAdvisor", () => ({
  VoiceAdvisor: ({ pendingVoiceAction }: { pendingVoiceAction: string | null }) => (
    <div data-testid="voice-advisor-stub">{pendingVoiceAction ?? "none"}</div>
  ),
}));

describe("App keyboard shortcuts", () => {
  it("does not render VoiceAdvisor on the dashboard", async () => {
    render(<App />);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.queryByTestId("voice-advisor-stub")).not.toBeInTheDocument();
  });

  it("opens the Advisory modal and queues a greet action on Alt+A when closed", async () => {
    render(<App />);
    fireEvent.keyDown(window, { key: "a", altKey: true });

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByTestId("voice-advisor-stub")).toHaveTextContent("greet");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/App.test.tsx`
Expected: FAIL — `App.tsx` still renders `<VoiceAdvisor />` directly on the dashboard and has no Alt+A listener.

- [ ] **Step 3: Modify the implementation**

In `frontend/src/App.tsx`:

1. Remove the `VoiceAdvisor` import (currently line 39) — it's no longer used directly in `App.tsx`.

2. Add a `pendingVoiceAction` state next to `advisoryOpen` (currently line 79):

```ts
  const [advisoryOpen, setAdvisoryOpen] = useState(false);
  const [pendingVoiceAction, setPendingVoiceAction] = useState<"greet" | "demo" | null>(null);
```

3. Add a keyboard-shortcut effect. Place it near the other top-level `useEffect`s (after the one ending around line 92):

```ts
  useEffect(() => {
    const runVoiceShortcut = (event: KeyboardEvent) => {
      if (!event.altKey) return;
      const key = event.key.toLowerCase();
      if (key !== "a" && key !== "d") return;
      event.preventDefault();
      setAdvisoryOpen(true);
      setPendingVoiceAction(key === "a" ? "greet" : "demo");
    };

    window.addEventListener("keydown", runVoiceShortcut);
    return () => window.removeEventListener("keydown", runVoiceShortcut);
  }, []);
```

4. Remove the `<VoiceAdvisor />` render from the dashboard section (currently line 237):

```tsx
        <ComponentDock selected={selectedComponent} onSelect={setSelectedComponent} />

        <section className="car-stage" aria-label="Interactive Mercedes 3D valuation model">
```

(Delete the `<VoiceAdvisor />` line that previously sat between those two — no replacement needed there.)

5. Pass the new props to `AdvisoryModal` (currently lines 296-309):

```tsx
      <AdvisoryModal
        open={advisoryOpen}
        profile={dashboard.profile}
        prediction={dashboard.prediction}
        depreciation={dashboard.depreciation?.points ?? null}
        snapshot={dashboard.snapshot}
        faults={dashboard.faults}
        market={dashboard.market}
        pendingVoiceAction={pendingVoiceAction}
        onPendingVoiceActionHandled={() => setPendingVoiceAction(null)}
        onClose={() => setAdvisoryOpen(false)}
        onBookInspection={() => {
          setAdvisoryOpen(false);
          setBookingOpen(true);
        }}
      />
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/App.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS for every suite (Tasks 1-7).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "$(cat <<'EOF'
Scope voice assistant to the Advisory modal, keep Alt+A/D global

VoiceAdvisor no longer renders on the dashboard, so mic access only
happens while the modal is open. Alt+A/Alt+D still work when the
modal is closed: they open it and queue a pendingVoiceAction that
VoiceAdvisor consumes once mounted.
EOF
)"
```

---

### Task 8: Styling — status bar, visualizer bars, debug panel, cleanup

**Files:**
- Modify: `frontend/src/styles/theme.css`

- [ ] **Step 1: Replace `.voice-advisor`'s dashboard-absolute positioning with in-flow modal styling**

Replace the current block (lines 301-321):

```css
.voice-advisor {
  position: absolute;
  left: 50%;
  top: 116px;
  transform: translateX(-50%);
  z-index: 4;
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(7, 11, 12, 0.72);
  color: var(--text-dim);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 800;
  padding: 7px 11px;
  text-transform: uppercase;
  backdrop-filter: blur(10px);
}
```

with:

```css
.voice-advisor {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(7, 11, 12, 0.72);
  color: var(--text-dim);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 800;
  padding: 7px 11px;
  text-transform: uppercase;
  backdrop-filter: blur(10px);
  margin-bottom: 14px;
}
```

- [ ] **Step 2: Replace `.voice-advisor__response`'s absolute positioning with in-flow styling**

Replace the current block (lines 350-366):

```css
.voice-advisor__response {
  position: absolute;
  left: 50%;
  top: 160px;
  transform: translateX(-50%);
  z-index: 4;
  max-width: min(560px, calc(100vw - 32px));
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(7, 11, 12, 0.78);
  color: var(--text);
  font-size: 13px;
  line-height: 1.45;
  padding: 10px 12px;
  text-align: center;
  backdrop-filter: blur(10px);
}
```

with:

```css
.voice-advisor__response {
  max-width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(7, 11, 12, 0.78);
  color: var(--text);
  font-size: 13px;
  line-height: 1.45;
  padding: 10px 12px;
  text-align: center;
  backdrop-filter: blur(10px);
  margin-bottom: 14px;
}
```

- [ ] **Step 3: Add visualizer and in-modal debug panel styles**

Insert after the `.voice-advisor__response small` rule (currently ending at line 373):

```css
.voice-visualizer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 16px;
}

.voice-visualizer__bar {
  width: 3px;
  border-radius: 2px;
  background: var(--accent);
}

.voice-visualizer--idle .voice-visualizer__bar {
  height: 10px;
  animation: voice-visualizer-idle 1.6s ease-in-out infinite;
}

.voice-visualizer--idle .voice-visualizer__bar:nth-child(2),
.voice-visualizer--idle .voice-visualizer__bar:nth-child(6) {
  animation-delay: 0.15s;
}

.voice-visualizer--idle .voice-visualizer__bar:nth-child(3),
.voice-visualizer--idle .voice-visualizer__bar:nth-child(5) {
  animation-delay: 0.3s;
}

.voice-visualizer--idle .voice-visualizer__bar:nth-child(4) {
  animation-delay: 0.45s;
}

@keyframes voice-visualizer-idle {
  0%,
  100% {
    opacity: 0.45;
    transform: scaleY(0.6);
  }
  50% {
    opacity: 1;
    transform: scaleY(1);
  }
}

.voice-advisor__debug {
  margin-top: 10px;
  background: rgba(0, 0, 0, 0.85);
  color: #0f0;
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  max-width: 100%;
}
```

- [ ] **Step 4: Remove now-dead dashboard-grid references to `.voice-advisor`**

In the `max-width` media query block, remove `.voice-advisor,` from the comma-separated selector list (currently lines 1672-1681):

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

Remove the now-orphaned rule (currently lines 1696-1698):

```css
  .voice-advisor {
    justify-self: center;
  }
```

(Delete that whole block — `.voice-advisor` is no longer a direct child of `.dashboard-stage`'s grid, so this rule has nothing to target.)

- [ ] **Step 5: Manually sanity-check the CSS file parses**

Run: `cd frontend && npx vite build --mode development 2>&1 | tail -30`
Expected: build proceeds past CSS processing without a "Unexpected token" / parse error for `theme.css` (unrelated build errors, if any, are out of scope for this task).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles/theme.css
git commit -m "$(cat <<'EOF'
Restyle voice advisor UI for in-modal layout

.voice-advisor and .voice-advisor__response move from dashboard-absolute
positioning to normal flow inside the Advisory modal. Adds
.voice-visualizer bar styles (reactive + idle-pulse) and an in-modal
debug panel style, and removes the now-dead dashboard-grid rules that
referenced .voice-advisor as a direct grid child.
EOF
)"
```

---

### Task 9: Manual verification in the browser

**Files:** none (verification only)

- [ ] **Step 1: Start the frontend dev server**

Use the preview tool to start the frontend dev server (per this project's existing `.claude/launch.json` configuration, or `npm run dev` inside `frontend/` if no launch config exists yet).

- [ ] **Step 2: Confirm the dashboard no longer shows the voice pill or debug panel**

Load the dashboard. Confirm there is no "Listening for wake phrase" pill and no green debug box anywhere on the page.

- [ ] **Step 3: Open the AI Advisory modal and confirm mic starts**

Click the "AI Advisory" button. Confirm the browser's mic-permission prompt appears (if not previously granted) and, once granted, the pill reading "Listening for wake phrase... Say Hey AssetIQ" appears inside the modal between the header and the "Sell or inspect first" hero section. Confirm the debug panel now renders inside the modal.

- [ ] **Step 4: Confirm the wake phrase swaps the pill for the visualizer**

Say "Hey AssetIQ." Confirm the pill is replaced by 7 vertical bars, and that talking louder/softer while it's listening for your question visibly changes bar heights. Confirm bars also animate during the spoken response.

- [ ] **Step 5: Confirm returning to idle brings the pill back**

Let a follow-up window expire (or say something unrelated that routes back to `waiting_for_wake`). Confirm the bars revert to the pill.

- [ ] **Step 6: Confirm mic access stops when the modal closes**

Close the Advisory modal. Confirm the browser's mic-in-use indicator (tab/address-bar icon) turns off.

- [ ] **Step 7: Confirm Alt+A/Alt+D work with the modal closed**

Close the modal if open. Press Alt+A. Confirm the modal opens and the greeting plays. Close it again, press Alt+D, confirm the demo question flow runs.

- [ ] **Step 8: Report results**

Summarize pass/fail for each of the above to the user, including a screenshot of the modal mid-visualizer state if the preview tooling supports it.

---

## Plan self-review notes

- **Spec coverage:** Goal 1 (mic scoped to modal) → Tasks 5-7. Goal 2 (Alt+A/D work when closed) → Tasks 5, 7. Goal 3 (pill/visualizer + debug panel move into modal) → Tasks 5, 6, 8. Goal 4 (pill vs. visualizer state mapping) → Tasks 1, 5. Goal 5 (real audio-reactive bars + idle fallback) → Tasks 2, 3, 5.
- **Type consistency:** `"greet" | "demo" | null` is used identically as the `pendingVoiceAction` type across `App.tsx`, `AdvisoryModal.tsx`, and `VoiceAdvisor.tsx`. `VoiceLevelSource` (`"mic" | "playback" | "idle"`) is defined once in `voiceVisualizerLogic.ts` and consumed only there and in `VoiceAdvisor.tsx`'s destructuring — not re-declared elsewhere.
- **No placeholders:** every step above contains complete, runnable code.
