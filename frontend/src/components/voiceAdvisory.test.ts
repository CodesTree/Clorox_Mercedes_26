import { afterEach, expect, test, vi } from "vitest";
import {
  getAdvisoryAnswer,
  getIsSpeaking,
  isUsableQuestionTranscript,
  isWakePhrase,
  normalizeTranscript,
  speakAssistant,
  stopAllVoice,
} from "./voiceAdvisory";

afterEach(() => {
  stopAllVoice();
  vi.unstubAllGlobals();
});

function stubBlobUrls() {
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:test-audio"),
    revokeObjectURL: vi.fn(),
  });
}

test("answers repair versus trade-in questions from the mock advisory data", () => {
  expect(getAdvisoryAnswer("Should I sell my car now?")).toBe(
    "Based on your current value of RM82,000 and estimated repair cost of RM12,000, trading in is recommended because repairing leaves an outcome of RM76,000 compared with RM82,000 if you trade in now.",
  );
});

test("keeps outside questions inside the advisory scope", () => {
  expect(getAdvisoryAnswer("Can you book my appointment?")).toBe(
    "I can only help explain this repair versus trade-in advisory right now.",
  );
});

test("answers scoped conversational follow-ups in the local fallback", () => {
  expect(getAdvisoryAnswer("thanks")).toBe(
    "You're welcome. Say Hey AssetIQ if you want to ask more about the advisory.",
  );
  expect(getAdvisoryAnswer("why")).toBe(
    "Trade-in is recommended because the estimated repair cost is RM12,000, and repairing leaves an outcome of RM76,000 compared with RM82,000 if you trade in now.",
  );
});

test("normalizes transcripts and detects common wake phrase variants", () => {
  expect(normalizeTranscript("Hey, Asset I.Q.!")).toBe("hey asset i q");
  expect(isWakePhrase("hey assetiq")).toBe(true);
  expect(isWakePhrase("hey asset iq")).toBe(true);
  expect(isWakePhrase("hey asset i q")).toBe(true);
  expect(isWakePhrase("AssetIQ")).toBe(true);
  expect(isWakePhrase("asset iq")).toBe(true);
  expect(isWakePhrase("hey assets iq")).toBe(true);
  expect(isWakePhrase("hey i said iq")).toBe(true);
  expect(isWakePhrase("hey is that iq")).toBe(true);
  expect(isWakePhrase("repair cost")).toBe(false);
});

test("accepts only real non-wake question transcripts", () => {
  expect(isUsableQuestionTranscript("")).toBe(false);
  expect(isUsableQuestionTranscript("   ")).toBe(false);
  expect(isUsableQuestionTranscript("thanks")).toBe(true);
  expect(isUsableQuestionTranscript("thank you")).toBe(true);
  expect(isUsableQuestionTranscript("ok")).toBe(true);
  expect(isUsableQuestionTranscript("okay")).toBe(true);
  expect(isUsableQuestionTranscript("got it")).toBe(true);
  expect(isUsableQuestionTranscript("why")).toBe(true);
  expect(isUsableQuestionTranscript("explain")).toBe(true);
  expect(isUsableQuestionTranscript("explain again")).toBe(true);
  expect(isUsableQuestionTranscript("what do you mean")).toBe(true);
  expect(isUsableQuestionTranscript("Hey AssetIQ")).toBe(false);
  expect(isUsableQuestionTranscript("asset iq")).toBe(false);
  expect(isUsableQuestionTranscript("Should I sell my car now?")).toBe(true);
  expect(isUsableQuestionTranscript("Tell me a joke")).toBe(true);
});

test("plays only backend audio when base64 audio exists", () => {
  const play = vi.fn().mockResolvedValue(undefined);
  const AudioStub = vi.fn().mockImplementation(() => ({ play, pause: vi.fn(), currentTime: 0 }));
  stubBlobUrls();
  vi.stubGlobal("Audio", AudioStub);

  const started = speakAssistant({
    text: "Trade in now.",
    audioBase64: "UklGRg==",
    mimeType: "audio/wav",
    onStart: vi.fn(),
    onEnd: vi.fn(),
    onPlaybackError: vi.fn(),
  });

  expect(started).toBe(true);
  expect(AudioStub).toHaveBeenCalledWith(expect.stringMatching(/^blob:/));
  expect(play).toHaveBeenCalled();
});

test("does not use browser speech when Gemini audio is missing", () => {
  const AudioStub = vi.fn();
  const speak = vi.fn();
  vi.stubGlobal("Audio", AudioStub);
  vi.stubGlobal("speechSynthesis", { cancel: vi.fn(), speak });
  vi.stubGlobal("SpeechSynthesisUtterance", vi.fn().mockImplementation((text) => ({ text })));
  const onEnd = vi.fn();
  const onPlaybackError = vi.fn();

  const started = speakAssistant({
    text: "Trade in now.",
    audioBase64: null,
    mimeType: null,
    onStart: vi.fn(),
    onEnd,
    onPlaybackError,
  });

  expect(started).toBe(false);
  expect(AudioStub).not.toHaveBeenCalled();
  expect(speak).not.toHaveBeenCalled();
  expect(onPlaybackError).not.toHaveBeenCalled();
  expect(onEnd).not.toHaveBeenCalled();
});

test("speaking guard prevents overlapping speech", () => {
  const play = vi.fn().mockResolvedValue(undefined);
  stubBlobUrls();
  vi.stubGlobal("Audio", vi.fn().mockImplementation(() => ({ play, pause: vi.fn(), currentTime: 0 })));
  vi.stubGlobal("speechSynthesis", { cancel: vi.fn() });

  const options = {
    text: "Trade in now.",
    audioBase64: "UklGRg==",
    mimeType: "audio/wav",
    onStart: vi.fn(),
    onEnd: vi.fn(),
    onPlaybackError: vi.fn(),
  };

  expect(speakAssistant(options)).toBe(true);
  expect(getIsSpeaking()).toBe(true);
  expect(speakAssistant(options)).toBe(false);
});

test("passes the created Audio element to onAudioElement before playback starts", () => {
  const play = vi.fn().mockResolvedValue(undefined);
  stubBlobUrls();
  vi.stubGlobal(
    "Audio",
    vi.fn().mockImplementation(() => ({ play, pause: vi.fn(), currentTime: 0 })),
  );
  let receivedElement: unknown = null;

  const started = speakAssistant({
    text: "Trade in now.",
    audioBase64: "UklGRg==",
    mimeType: "audio/wav",
    onStart: vi.fn(),
    onEnd: vi.fn(),
    onPlaybackError: vi.fn(),
    onAudioElement: (element) => {
      receivedElement = element;
    },
  });

  expect(started).toBe(true);
  expect(receivedElement).not.toBeNull();
  expect(play).toHaveBeenCalled();
});
