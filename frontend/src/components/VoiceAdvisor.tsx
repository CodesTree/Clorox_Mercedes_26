import { useEffect, useRef, useState } from "react";
import type { AdvisoryVoiceResponse } from "../api/client";
import { respondToAdvisoryVoice } from "../api/client";
import {
  getAdvisoryAnswer,
  getIsSpeaking,
  isUsableQuestionTranscript,
  isWakePhrase,
  mockAdvisoryData,
  normalizeTranscript,
  speakAssistant,
  stopAllVoice,
} from "./voiceAdvisory";
import { useMicLevel, usePlaybackLevel } from "./voiceAudioLevel";
import { VoiceVisualizer } from "./VoiceVisualizer";
import { isPillState, levelSourceForState } from "./voiceVisualizerLogic";

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

type RecognitionMode = "wake" | "question" | "followup";
type RecognitionDebugMode = RecognitionMode | "waiting_for_followup";
type RecognitionState = "idle" | "listening" | "stopped" | "error";

interface SpeechRecognitionResultItem {
  transcript: string;
}

interface SpeechRecognitionResult {
  readonly length: number;
  readonly isFinal: boolean;
  item(index: number): SpeechRecognitionResultItem;
  [index: number]: SpeechRecognitionResultItem;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

const wakePhrase = "hey assetiq";
const greeting = "Hi, what can I help?";
const demoQuestion = "Should I sell my car now?";
const fillerText = "Let me think for a moment.";
const maxQuestionListenRetries = 2;
const questionListenRetryDelayMs = 300;
const followupWindowMs = 12000;
const fillerDisplayMs = 1200;

function getSpeechRecognition() {
  return window.SpeechRecognition ?? window.webkitSpeechRecognition;
}

function getDebugMode(mode: RecognitionMode): RecognitionDebugMode {
  return mode === "followup" ? "waiting_for_followup" : mode;
}

interface VoiceAdvisorProps {
  pendingVoiceAction: "greet" | "demo" | null;
  onPendingVoiceActionHandled: () => void;
}

export function VoiceAdvisor({ pendingVoiceAction, onPendingVoiceActionHandled }: VoiceAdvisorProps) {
  const [voiceState, setVoiceState] = useState<VoiceState>("waiting_for_wake");
  const [debugInfo, setDebugInfo] = useState({
    rawTranscript: "",
    normalized: "",
    matched: false,
    mode: "wake" as RecognitionDebugMode,
    recognitionState: "idle" as RecognitionState,
    questionRetry: 0,
    lastEvent: "idle",
    lifecycle: "waiting_for_wake",
    lastReply: "",
    audioBase64Length: 0,
    ttsProvider: "",
    fallbackReason: "",
    playbackPath: "",
    playbackError: "",
  });
  const [assistantText, setAssistantText] = useState("");
  const [voiceStatusMessage, setVoiceStatusMessage] = useState("");
  const [activeAudioElement, setActiveAudioElement] = useState<HTMLAudioElement | null>(null);
  const modeRef = useRef<RecognitionMode>("wake");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const recognitionActiveRef = useRef(false);
  const pendingStartModeRef = useRef<RecognitionMode | null>(null);
  const recognitionHadResultRef = useRef(false);
  const questionListenRetryRef = useRef(0);
  const questionRetryTimeoutRef = useRef<number | null>(null);
  const generatingVoiceTimeoutRef = useRef<number | null>(null);
  const textOnlyTimeoutRef = useRef<number | null>(null);
  const followupTimeoutRef = useRef<number | null>(null);
  const fillerAudioCacheRef = useRef<AdvisoryVoiceResponse | null>(null);
  const isUnmountedRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const speechReservedRef = useRef(false);
  const lastQuestionTranscriptRef = useRef("");

  const stopRecognition = () => {
    try {
      recognitionRef.current?.stop();
    } catch {
      // Recognition may already be stopped by the browser.
    }
    recognitionActiveRef.current = false;
  };

  const startOneShotRecognition = (mode: RecognitionMode) => {
    const recognition = recognitionRef.current;
    if (!recognition || isUnmountedRef.current) return;
    if (recognitionActiveRef.current) {
      pendingStartModeRef.current = mode;
      return;
    }

    pendingStartModeRef.current = null;
    recognitionHadResultRef.current = false;
    modeRef.current = mode;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    setVoiceState(
      mode === "wake" ? "waiting_for_wake" : mode === "followup" ? "waiting_for_followup" : "waiting_for_question",
    );
    setDebugInfo((prev) => ({
      ...prev,
      mode: getDebugMode(mode),
      questionRetry: mode === "question" ? questionListenRetryRef.current : 0,
      lastEvent: `${mode}_start_requested`,
    }));
    console.log(`[voice] one-shot recognition starting: ${mode}`);

    try {
      recognition.start();
    } catch (error) {
      console.warn("[voice] recognition start failed", error);
      recognitionActiveRef.current = false;
      setDebugInfo((prev) => ({ ...prev, recognitionState: "error" }));
    }
  };

  const clearFollowupTimeout = () => {
    if (followupTimeoutRef.current !== null) {
      window.clearTimeout(followupTimeoutRef.current);
      followupTimeoutRef.current = null;
    }
  };

  const startQuestionRecognition = (options: { followup?: boolean } = {}) => {
    if (questionRetryTimeoutRef.current !== null) {
      window.clearTimeout(questionRetryTimeoutRef.current);
      questionRetryTimeoutRef.current = null;
    }
    if (textOnlyTimeoutRef.current !== null) {
      window.clearTimeout(textOnlyTimeoutRef.current);
      textOnlyTimeoutRef.current = null;
    }
    questionListenRetryRef.current = 0;
    const mode: RecognitionMode = options.followup ? "followup" : "question";
    modeRef.current = mode;
    setVoiceState(options.followup ? "waiting_for_followup" : "waiting_for_question");
    if (options.followup) {
      console.log("[voice] lifecycle: waiting_for_followup");
      setDebugInfo((prev) => ({ ...prev, lifecycle: "waiting_for_followup", mode: "waiting_for_followup" }));
      clearFollowupTimeout();
      followupTimeoutRef.current = window.setTimeout(() => {
        followupTimeoutRef.current = null;
        console.log("[voice] follow-up listen expired; returning to wake");
        returnToWake("followup_window_expired");
      }, followupWindowMs);
    }
    console.log(options.followup ? "[voice] starting follow-up recognition" : "[voice] starting question recognition after greeting");
    startOneShotRecognition(mode);
  };

  const retryQuestionRecognition = () => {
    questionListenRetryRef.current += 1;
    const retryCount = questionListenRetryRef.current;
    console.log(`[voice] question ended without transcript; retrying question listen ${retryCount}/${maxQuestionListenRetries}`);
    console.log("[voice] retrying question recognition");
    setVoiceState("waiting_for_question");
    setDebugInfo((prev) => ({
      ...prev,
      mode: "question",
      recognitionState: "stopped",
      questionRetry: retryCount,
      lastEvent: "question_end_without_result",
    }));

    questionRetryTimeoutRef.current = window.setTimeout(() => {
      questionRetryTimeoutRef.current = null;
      startOneShotRecognition("question");
    }, questionListenRetryDelayMs);
  };

  const reserveSpeech = () => {
    if (speechReservedRef.current || isSpeakingRef.current || getIsSpeaking()) return false;
    speechReservedRef.current = true;
    stopRecognition();
    return true;
  };

  const onSpeechStart = (options: { answer?: boolean } = {}) => {
    speechReservedRef.current = false;
    isSpeakingRef.current = true;
    setVoiceState("speaking");
    setDebugInfo((prev) => ({ ...prev, lifecycle: "speaking", playbackPath: "gemini-audio" }));
    console.log("[voice] lifecycle: speaking");
    console.log("[voice] gemini audio started");
    if (options.answer) {
      console.log("[voice] answer audio started");
    }
    stopRecognition();
  };

  const onSpeechEnd = (onEnd?: () => void) => {
    speechReservedRef.current = false;
    isSpeakingRef.current = false;
    setActiveAudioElement(null);
    onEnd?.();
  };

  const finishTextOnlyAfterDelay = (onEnd?: () => void) => {
    textOnlyTimeoutRef.current = window.setTimeout(() => {
      textOnlyTimeoutRef.current = null;
      onSpeechEnd(onEnd);
    }, 2500);
  };

  const handleNoGeminiAudio = (response: AdvisoryVoiceResponse, onEnd?: () => void) => {
    console.log("[voice] no Gemini audio returned");
    console.log("[voice] tts_provider:", response.tts_provider);
    console.log("[voice] fallback_reason:", response.fallback_reason);
    console.log("[voice] playback path: no-audio-gemini-unavailable");
    speechReservedRef.current = false;
    isSpeakingRef.current = false;
    setAssistantText(response.reply);
    setVoiceStatusMessage("Gemini voice unavailable. Text response shown.");
    setVoiceState("text_only");
    setDebugInfo((prev) => ({
      ...prev,
      lifecycle: "text_only",
      lastReply: response.reply,
      audioBase64Length: 0,
      ttsProvider: response.tts_provider,
      fallbackReason: response.fallback_reason ?? "",
      playbackPath: "no-audio-gemini-unavailable",
      playbackError: "",
    }));
    finishTextOnlyAfterDelay(onEnd);
  };

  const handlePlaybackError = (error: unknown, onEnd?: () => void) => {
    console.warn("[voice] Gemini audio playback error", error);
    speechReservedRef.current = false;
    isSpeakingRef.current = false;
    setVoiceStatusMessage("Gemini audio playback failed. Text response shown.");
    setVoiceState("playback_error");
    setDebugInfo((prev) => ({
      ...prev,
      lifecycle: "playback_error",
      playbackPath: "no-audio-gemini-unavailable",
      playbackError: error instanceof Error ? error.message : String(error),
    }));
    finishTextOnlyAfterDelay(onEnd);
  };

  const playFiller = async () => {
    setAssistantText("Let me think for a moment...");
    setVoiceStatusMessage("");
    setVoiceState("filler");
    setDebugInfo((prev) => ({ ...prev, lifecycle: "filler", lastReply: fillerText }));
    console.log("[voice] lifecycle: filler");
    console.log("[voice] filler tts requested");
    console.log("[voice] filler started");

    const cachedFiller = fillerAudioCacheRef.current;
    if (!cachedFiller?.audio_base64) {
      void respondToAdvisoryVoice(fillerText, mockAdvisoryData)
        .then((fillerResponse) => {
          if (fillerResponse.audio_base64 && !fillerAudioCacheRef.current) {
            fillerAudioCacheRef.current = fillerResponse;
            console.log("[voice] filler audio cached");
          }
        })
        .catch((error) => console.warn("[voice] filler tts failed", error));

      return new Promise<void>((resolve) => {
        window.setTimeout(() => {
          console.log("[voice] filler ended");
          resolve();
        }, fillerDisplayMs);
      });
    }

    return new Promise<void>((resolve) => {
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
      if (!didStart) {
        console.log("[voice] filler ended");
        resolve();
      }
    });
  };

  const speakResponse = (
    response: AdvisoryVoiceResponse,
    fallbackText: string,
    onEnd?: () => void,
    options: { answer?: boolean } = {},
  ) => {
    const text = response.reply || fallbackText;
    const audioLength = response.audio_base64?.length ?? 0;
    console.log("[voice] response reply:", text);
    console.log("[voice] tts_provider:", response.tts_provider);
    console.log("[voice] fallback_reason:", response.fallback_reason);
    console.log("[voice] mime_type:", response.mime_type);
    console.log("[voice] audio_base64 length:", audioLength);
    if (options.answer) {
      console.log("[voice] lifecycle: generating_voice");
    }
    setAssistantText(text);
    setVoiceStatusMessage("");
    setDebugInfo((prev) => ({
      ...prev,
      lifecycle: "generating_voice",
      lastReply: text,
      audioBase64Length: audioLength,
      ttsProvider: response.tts_provider,
      fallbackReason: response.fallback_reason ?? "",
      playbackPath: audioLength > 0 ? "gemini-audio" : "no-audio-gemini-unavailable",
      playbackError: "",
    }));

    if (!response.audio_base64) {
      handleNoGeminiAudio({ ...response, reply: text }, onEnd);
      return;
    }

    const didStart = speakAssistant({
      text,
      audioBase64: response.audio_base64,
      mimeType: response.mime_type,
      onStart: () => onSpeechStart({ answer: options.answer }),
      onAudioElement: setActiveAudioElement,
      onEnd: () => onSpeechEnd(onEnd),
      onPlaybackError: (error) => handlePlaybackError(error, onEnd),
    });
    if (!didStart) {
      speechReservedRef.current = false;
      handlePlaybackError("Gemini audio playback did not start", onEnd);
    }
  };

  const speakWithBackend = async (
    question: string,
    fallbackText: string,
    onEnd?: () => void,
    options: { answer?: boolean; waitForFiller?: Promise<void>; skipReserve?: boolean } = {},
  ) => {
    if (!options.skipReserve && !reserveSpeech()) return;
    let responseReturned = false;

    const startVisibleWait = () => {
      if (responseReturned || generatingVoiceTimeoutRef.current !== null) return;
      console.log("[voice] lifecycle: thinking");
      setVoiceState("answering");
      setDebugInfo((prev) => ({ ...prev, lifecycle: "thinking" }));
      generatingVoiceTimeoutRef.current = window.setTimeout(() => {
        generatingVoiceTimeoutRef.current = null;
        console.log("[voice] lifecycle: generating_voice");
        setVoiceState("generating_voice");
        setDebugInfo((prev) => ({ ...prev, lifecycle: "generating_voice" }));
      }, 900);
    };

    try {
      const responsePromise = respondToAdvisoryVoice(question, mockAdvisoryData).then((response) => {
        responseReturned = true;
        return response;
      });
      if (options.waitForFiller) {
        await options.waitForFiller;
      }
      if (options.answer) {
        startVisibleWait();
      }
      const response = await responsePromise;
      if (generatingVoiceTimeoutRef.current !== null) {
        window.clearTimeout(generatingVoiceTimeoutRef.current);
        generatingVoiceTimeoutRef.current = null;
      }
      if (options.answer && response.audio_base64) {
        console.log("[voice] answer audio ready");
        console.log("[voice] answer audio queued");
      }
      await options.waitForFiller;
      speakResponse(response, fallbackText, onEnd, { answer: options.answer });
    } catch {
      if (generatingVoiceTimeoutRef.current !== null) {
        window.clearTimeout(generatingVoiceTimeoutRef.current);
        generatingVoiceTimeoutRef.current = null;
      }
      await options.waitForFiller;
      if (options.answer) {
        startVisibleWait();
      }
      handleNoGeminiAudio(
        {
          reply: fallbackText,
          audio_base64: null,
          mime_type: null,
          tts_provider: "gemini-unavailable",
          fallback_reason: "backend_request_failed",
          text_provider: "local",
          tts_wait_ms: 0,
          gemini_key_detected: false,
        },
        onEnd,
      );
    }
  };

  const answerQuestion = (question: string, options: { demo?: boolean } = {}) => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      console.log("[voice] ignored unusable question");
      return;
    }
    if (speechReservedRef.current || isSpeakingRef.current || getIsSpeaking()) return;
    lastQuestionTranscriptRef.current = "";
    console.log(options.demo ? "[voice] demo shortcut question sent:" : "[voice] sending real question:", trimmedQuestion);
    if (!reserveSpeech()) return;
    setVoiceState("answering");
    const fillerDone = playFiller();
    void speakWithBackend(trimmedQuestion, getAdvisoryAnswer(trimmedQuestion), () => {
      startQuestionRecognition({ followup: true });
    }, { answer: true, waitForFiller: fillerDone, skipReserve: true });
  };

  const returnToWake = (lastEvent = "returned_to_wake") => {
    if (questionRetryTimeoutRef.current !== null) {
      window.clearTimeout(questionRetryTimeoutRef.current);
      questionRetryTimeoutRef.current = null;
    }
    questionListenRetryRef.current = 0;
    clearFollowupTimeout();
    modeRef.current = "wake";
    setVoiceState("waiting_for_wake");
    setDebugInfo((prev) => ({ ...prev, mode: "wake", questionRetry: 0, lastEvent, lifecycle: "waiting_for_wake" }));
    console.log("[voice] returned to waiting_for_wake");
    startOneShotRecognition("wake");
  };

  const handleQuestionTranscript = (rawTranscript: string) => {
    const trimmedTranscript = rawTranscript.trim();
    const normalizedTranscript = normalizeTranscript(trimmedTranscript);
    console.log("[voice] question transcript heard:", trimmedTranscript);

    if (!normalizedTranscript || !isUsableQuestionTranscript(normalizedTranscript)) {
      console.log("[voice] ignored unusable question");
      lastQuestionTranscriptRef.current = "";
      returnToWake();
      return;
    }

    lastQuestionTranscriptRef.current = trimmedTranscript;
    clearFollowupTimeout();
    answerQuestion(trimmedTranscript);
  };

  const greet = (onReady?: () => void) => {
    if (speechReservedRef.current || isSpeakingRef.current || getIsSpeaking()) return;
    modeRef.current = "question";
    setVoiceState("greeting");
    void speakWithBackend(wakePhrase, greeting, () => {
      console.log("[voice] greeting finished");
      lastQuestionTranscriptRef.current = "";
      startQuestionRecognition();
      onReady?.();
    });
  };

  useEffect(() => {
    isUnmountedRef.current = false;
    const Recognition = getSpeechRecognition();
    if (!Recognition) {
      setVoiceState("unsupported");
      return undefined;
    }

    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      recognitionActiveRef.current = true;
      recognitionHadResultRef.current = false;
      console.log("[voice] recognition started");
      if (modeRef.current === "question") {
        console.log("[voice] question recognition started");
      }
      setDebugInfo((prev) => ({
        ...prev,
        mode: getDebugMode(modeRef.current),
        recognitionState: "listening",
        questionRetry: modeRef.current === "question" ? questionListenRetryRef.current : 0,
        lastEvent: modeRef.current === "question" ? "question_recognition_started" : "wake_recognition_started",
      }));
    };
    recognition.onresult = (event) => {
      const rawTranscript = event.results[event.results.length - 1]?.[0]?.transcript ?? "";
      recognitionHadResultRef.current = true;
      setDebugInfo((prev) => ({
        ...prev,
        rawTranscript,
        normalized: normalizeTranscript(rawTranscript),
        matched: isWakePhrase(rawTranscript),
        mode: getDebugMode(modeRef.current),
        recognitionState: "listening",
        questionRetry: modeRef.current === "question" ? questionListenRetryRef.current : 0,
        lastEvent: "result",
      }));
      if (isSpeakingRef.current || getIsSpeaking()) {
        console.log("[voice] ignoring transcript, assistant is speaking");
        return;
      }

      const latest = normalizeTranscript(rawTranscript);
      if (modeRef.current === "wake") {
        console.log("[voice] wake transcript heard:", rawTranscript);
        if (!latest) {
          pendingStartModeRef.current = "wake";
          stopRecognition();
          return;
        }

        if (isWakePhrase(latest)) {
          console.log("[voice] wake matched");
          stopRecognition();
          greet();
        } else {
          console.log("[voice] wake phrase not matched");
          pendingStartModeRef.current = "wake";
          stopRecognition();
        }
        return;
      }

      stopRecognition();
      handleQuestionTranscript(rawTranscript);
    };

    recognition.onerror = (event) => {
      console.warn("[voice] recognition error", event.error);
      setDebugInfo((prev) => ({ ...prev, recognitionState: "error", lastEvent: "error" }));
    };
    recognition.onend = () => {
      console.log("[voice] recognition ended");
      recognitionActiveRef.current = false;
      setDebugInfo((prev) => ({ ...prev, recognitionState: "stopped", lastEvent: `${modeRef.current}_ended` }));

      if (isUnmountedRef.current || isSpeakingRef.current || getIsSpeaking() || speechReservedRef.current) {
        return;
      }

      if (modeRef.current === "question" && !recognitionHadResultRef.current) {
        console.log("[voice] question ended without transcript");
        if (questionListenRetryRef.current < maxQuestionListenRetries) {
          retryQuestionRecognition();
          return;
        }

        console.log("[voice] question listen expired; returning to wake");
        setDebugInfo((prev) => ({
          ...prev,
          recognitionState: "stopped",
          questionRetry: maxQuestionListenRetries,
          lastEvent: "question_listen_expired",
        }));
        returnToWake("question_listen_expired");
        return;
      }

      const nextMode = pendingStartModeRef.current ?? modeRef.current;
      pendingStartModeRef.current = null;
      console.log("[voice] auto re-arming recognition:", nextMode);
      startOneShotRecognition(nextMode);
    };

    startOneShotRecognition("wake");

    return () => {
      isUnmountedRef.current = true;
      pendingStartModeRef.current = null;
      if (questionRetryTimeoutRef.current !== null) {
        window.clearTimeout(questionRetryTimeoutRef.current);
        questionRetryTimeoutRef.current = null;
      }
      if (generatingVoiceTimeoutRef.current !== null) {
        window.clearTimeout(generatingVoiceTimeoutRef.current);
        generatingVoiceTimeoutRef.current = null;
      }
      if (textOnlyTimeoutRef.current !== null) {
        window.clearTimeout(textOnlyTimeoutRef.current);
        textOnlyTimeoutRef.current = null;
      }
      clearFollowupTimeout();
      stopAllVoice();
      recognition.onstart = null;
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      stopRecognition();
      recognitionRef.current = null;
      recognitionActiveRef.current = false;
    };
  }, []);

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

  const levelSource = levelSourceForState(voiceState);
  const micLevel = useMicLevel(levelSource === "mic");
  const playbackLevel = usePlaybackLevel(levelSource === "playback" ? activeAudioElement : null);
  const { level, idle } =
    levelSource === "mic" ? micLevel : levelSource === "playback" ? playbackLevel : { level: 0, idle: true };

  const label =
    voiceState === "unsupported"
      ? "Voice demo shortcut ready"
      : voiceState === "filler"
        ? "Let me think for a moment..."
      : voiceState === "answering"
        ? "Thinking..."
        : voiceState === "generating_voice"
          ? "Generating voice..."
          : voiceState === "text_only"
            ? "Text response shown"
            : voiceState === "playback_error"
              ? "Gemini playback failed"
              : voiceState === "waiting_for_followup"
                ? "Listening for follow-up..."
              : voiceState === "waiting_for_question"
                ? "Listening for advisory question"
                : voiceState === "greeting" || voiceState === "speaking"
                  ? "Speaking..."
                  : "Listening for wake phrase... Say Hey AssetIQ.";

  return (
    <>
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
      {assistantText ? (
        <div className="voice-advisor__response" aria-live="polite">
          <div>{assistantText}</div>
          {voiceStatusMessage ? <small>{voiceStatusMessage}</small> : null}
        </div>
      ) : null}
      <div className="voice-advisor__debug">
        {voiceState === "waiting_for_followup" && debugInfo.recognitionState === "listening" ? (
          <div>Listening for follow-up...</div>
        ) : null}
        {voiceState === "waiting_for_question" && debugInfo.recognitionState === "listening" ? (
          <div>Listening for your question...</div>
        ) : null}
        <div>voice: {voiceState}</div>
        <div>lifecycle: {debugInfo.lifecycle}</div>
        <div>state: {debugInfo.recognitionState}</div>
        <div>mode: {debugInfo.mode}</div>
        <div>
          question retry: {debugInfo.questionRetry}/{maxQuestionListenRetries}
        </div>
        <div>last event: {debugInfo.lastEvent}</div>
        <div>heard: "{debugInfo.rawTranscript}"</div>
        <div>normalized: "{debugInfo.normalized}"</div>
        <div>matched: {debugInfo.matched ? "yes" : "no"}</div>
        <div>last reply: "{debugInfo.lastReply}"</div>
        <div>audio_base64 length: {debugInfo.audioBase64Length}</div>
        <div>tts_provider: {debugInfo.ttsProvider}</div>
        <div>fallback_reason: {debugInfo.fallbackReason}</div>
        <div>playback path: {debugInfo.playbackPath}</div>
        <div>playback error: {debugInfo.playbackError}</div>
      </div>
    </>
  );
}
