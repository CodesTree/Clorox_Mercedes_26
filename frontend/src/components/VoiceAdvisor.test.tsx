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
