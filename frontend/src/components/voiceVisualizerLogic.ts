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
