import type { AdvisoryData } from "../api/client";

export const mockAdvisoryData: AdvisoryData = {
  current_value_rm: 82000,
  estimated_repair_cost_rm: 12000,
  predicted_value_after_repair_rm: 88000,
  repair_outcome_rm: 76000,
  trade_in_now_rm: 82000,
  recommendation: "trade_in",
  summary:
    "Based on your car's current value and estimated repair cost, trading in is recommended because the repair cost is too high compared to the value recovered after repair.",
};

const advisoryTerms = [
  "advisory",
  "car",
  "cost",
  "fix",
  "repair",
  "sell",
  "trade",
  "trade-in",
  "trade in",
  "value",
  "worth",
];

const outsideAdvisoryReply = "I can only help explain this repair versus trade-in advisory right now.";
const thanksReply = "You're welcome. Say Hey AssetIQ if you want to ask more about the advisory.";
const wakePhrasePatterns = [
  /\bassetiq\b/,
  /\basset\s+iq\b/,
  /\basset\s+i\s+q\b/,
  /\bhey\s+assetiq\b/,
  /\bhey\s+asset\s+iq\b/,
  /\bhey\s+asset\s+i\s+q\b/,
  /\bhey\s+assets\s+iq\b/,
  /\bhey\s+i\s+said\s+iq\b/,
  /\bhey\s+is\s+that\s+iq\b/,
];
const conversationalQuestionPatterns = [
  /\bhi\b/,
  /\bhello\b/,
  /\bthanks\b/,
  /\bthank\s+you\b/,
  /\bok\b/,
  /\bokay\b/,
  /\bgot\s+it\b/,
  /\bwhy\b/,
  /\bexplain\b/,
  /\bexplain\s+again\b/,
  /\bwhat\s+do\s+you\s+mean\b/,
];
const minQuestionLength = 3;
let currentAudio: HTMLAudioElement | null = null;
let isSpeaking = false;

interface SpeakAssistantOptions {
  text: string;
  audioBase64?: string | null;
  mimeType?: string | null;
  onStart: () => void;
  onEnd: () => void;
  onPlaybackError: (error: unknown) => void;
  onAudioElement?: (audio: HTMLAudioElement) => void;
}

function formatRm(value: number) {
  return `RM${value.toLocaleString("en-MY")}`;
}

function getRecommendationReason(advisory: AdvisoryData) {
  if (advisory.recommendation === "trade_in") {
    return `Trade-in is recommended because the estimated repair cost is ${formatRm(
      advisory.estimated_repair_cost_rm,
    )}, and repairing leaves an outcome of ${formatRm(advisory.repair_outcome_rm)} compared with ${formatRm(
      advisory.trade_in_now_rm,
    )} if you trade in now.`;
  }

  return advisory.summary;
}

export function normalizeTranscript(transcript: string) {
  return transcript
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function isWakePhrase(transcript: string) {
  const normalized = normalizeTranscript(transcript);
  return wakePhrasePatterns.some((pattern) => pattern.test(normalized));
}

export function isUsableQuestionTranscript(transcript: string) {
  const normalized = normalizeTranscript(transcript);
  if (!normalized || isWakePhrase(normalized)) return false;
  return (
    normalized.length >= minQuestionLength ||
    conversationalQuestionPatterns.some((pattern) => pattern.test(normalized))
  );
}

export function getIsSpeaking() {
  return isSpeaking;
}

export function getAdvisoryAnswer(question: string, advisory: AdvisoryData = mockAdvisoryData) {
  const normalized = normalizeTranscript(question);
  if (/\bthanks\b/.test(normalized) || /\bthank\s+you\b/.test(normalized)) {
    return thanksReply;
  }
  if (/\bwhy\b/.test(normalized) || /\bexplain\b/.test(normalized) || /\bwhat\s+do\s+you\s+mean\b/.test(normalized)) {
    return getRecommendationReason(advisory);
  }
  const isAdvisoryQuestion = advisoryTerms.some((term) => normalized.includes(term));

  if (!isAdvisoryQuestion) {
    return outsideAdvisoryReply;
  }

  if (advisory.recommendation === "trade_in") {
    return `Based on your current value of ${formatRm(
      advisory.current_value_rm,
    )} and estimated repair cost of ${formatRm(
      advisory.estimated_repair_cost_rm,
    )}, trading in is recommended because repairing leaves an outcome of ${formatRm(
      advisory.repair_outcome_rm,
    )} compared with ${formatRm(advisory.trade_in_now_rm)} if you trade in now.`;
  }

  return advisory.summary;
}

export function stopAudio(audio: HTMLAudioElement | null) {
  if (!audio) return;
  audio.pause();
  audio.currentTime = 0;
  audio.onended = null;
  audio.onerror = null;
}

export function stopAllVoice() {
  stopAudio(currentAudio);
  currentAudio = null;
  isSpeaking = false;
}

function base64ToBlobUrl(base64: string, mimeType: string) {
  const bytes = atob(base64);
  const byteNumbers = new Array<number>(bytes.length);
  for (let index = 0; index < bytes.length; index += 1) {
    byteNumbers[index] = bytes.charCodeAt(index);
  }
  return URL.createObjectURL(new Blob([new Uint8Array(byteNumbers)], { type: mimeType }));
}

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
