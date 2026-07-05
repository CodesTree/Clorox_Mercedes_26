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
