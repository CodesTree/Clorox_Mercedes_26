import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

class FakeAnalyserNode {
  fftSize = 256;
  frequencyBinCount: number;
  constructor(private readonly data: Uint8Array) {
    this.frequencyBinCount = data.length;
  }
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
