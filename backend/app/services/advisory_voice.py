from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
import wave
from dataclasses import dataclass
from typing import Any

import httpx
from app.config import get_settings
from app.schemas import AdvisoryData, AdvisoryVoiceResponse


logger = logging.getLogger(__name__)

OUTSIDE_ADVISORY_REPLY = "I can only help explain this repair versus trade-in advisory right now."
GREETING_REPLY = "Hi, what can I help?"
FILLER_REPLY = "Let me think for a moment."
THANKS_REPLY = "You\'re welcome. Say Hey AssetIQ if you want to ask more about the advisory."
DEFAULT_TTS_MODEL = "gemini-3.1-flash-tts-preview"
FALLBACK_TTS_MODEL = "gemini-2.5-flash-preview-tts"
TEXT_MODEL = "gemini-2.5-flash"
VOICE_NAME = "Kore"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
TTS_TIMEOUT_SECONDS = 14.0
_tts_quota_exhausted = False

ADVISORY_TERMS = (
    "advisory",
    "car",
    "cost",
    "graph",
    "mean",
    "fix",
    "repair",
    "recommend",
    "recommendation",
    "sell",
    "trade",
    "trade-in",
    "trade in",
    "value",
    "worth",
)

GRATITUDE_PATTERNS = (
    r"\bthanks\b",
    r"\bthank\s+you\b",
)
GREETING_PATTERNS = (
    r"\bhi\b",
    r"\bhello\b",
)
ACKNOWLEDGEMENT_PATTERNS = (
    r"\bok\b",
    r"\bokay\b",
    r"\bgot\s+it\b",
)
FOLLOW_UP_PATTERNS = (
    r"\bwhy\b",
    r"\bexplain\b",
    r"\bexplain\s+again\b",
    r"\bwhat\s+do\s+you\s+mean\b",
)


class GeminiRequestError(Exception):
    def __init__(self, status_code: int | None, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class GeminiTtsQuotaExceeded(Exception):
    pass


class GeminiTtsTimeout(Exception):
    pass


@dataclass(frozen=True)
class TtsAudio:
    audio_base64: str
    mime_type: str = "audio/wav"


_tts_audio_cache: dict[str, TtsAudio] = {}


def is_advisory_question(question: str) -> bool:
    normalized = question.strip().lower()
    return any(term in normalized for term in ADVISORY_TERMS)


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", question.lower())).strip()


def _matches_any(normalized: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, normalized) for pattern in patterns)


def format_rm(value: int) -> str:
    return f"RM{value:,}"


def fallback_reply(question: str, advisory: AdvisoryData) -> str:
    local_reply = fast_local_reply(question, advisory)
    if local_reply:
        return local_reply

    if not is_advisory_question(question):
        return OUTSIDE_ADVISORY_REPLY

    if advisory.recommendation == "trade_in":
        return (
            f"Based on your current value of {format_rm(advisory.current_value_rm)} and estimated "
            f"repair cost of {format_rm(advisory.estimated_repair_cost_rm)}, trading in is "
            "recommended because repairing does not recover enough value."
        )

    return advisory.summary


def _trade_in_answer(advisory: AdvisoryData) -> str:
    if advisory.recommendation == "trade_in":
        return (
            f"Based on your current value of {format_rm(advisory.current_value_rm)} and estimated "
            f"repair cost of {format_rm(advisory.estimated_repair_cost_rm)}, trading in is recommended because "
            f"repairing leaves an outcome of {format_rm(advisory.repair_outcome_rm)} compared with "
            f"{format_rm(advisory.trade_in_now_rm)} if you trade in now."
        )

    return advisory.summary


def _recommendation_reason(advisory: AdvisoryData) -> str:
    if advisory.recommendation == "trade_in":
        return (
            f"Trade-in is recommended because the estimated repair cost is {format_rm(advisory.estimated_repair_cost_rm)}, "
            f"and repairing leaves an outcome of {format_rm(advisory.repair_outcome_rm)} compared with "
            f"{format_rm(advisory.trade_in_now_rm)} if you trade in now."
        )

    return advisory.summary


def _asks_sell_or_trade(normalized: str) -> bool:
    return (
        "sell" in normalized
        or "trade in" in normalized
        or "trade" in normalized
        or "recommend" in normalized
        or "recommendation" in normalized
    )


def conversation_reply(question: str, advisory: AdvisoryData) -> str | None:
    normalized = _normalize_question(question)
    if not normalized:
        return None
    if normalized == "hey assetiq":
        return GREETING_REPLY
    if normalized == "let me think for a moment":
        return FILLER_REPLY
    if _matches_any(normalized, GRATITUDE_PATTERNS):
        return THANKS_REPLY
    if _matches_any(normalized, GREETING_PATTERNS):
        return GREETING_REPLY
    if _matches_any(normalized, ACKNOWLEDGEMENT_PATTERNS):
        return "Got it. Say Hey AssetIQ if you want to ask more about the advisory."
    if _matches_any(normalized, FOLLOW_UP_PATTERNS):
        return _recommendation_reason(advisory)
    return None


def fast_local_reply(question: str, advisory: AdvisoryData) -> str | None:
    normalized = _normalize_question(question)
    conversational = conversation_reply(question, advisory)
    if conversational:
        return conversational
    if _asks_sell_or_trade(normalized):
        return _trade_in_answer(advisory)
    if not is_advisory_question(question):
        return OUTSIDE_ADVISORY_REPLY
    return None


def _api_key() -> str | None:
    api_key = get_settings().gemini_api_key.strip()
    return api_key or None


def _tts_models() -> list[str]:
    configured = get_settings().gemini_tts_model.strip() or DEFAULT_TTS_MODEL
    models = [configured]
    if configured != FALLBACK_TTS_MODEL:
        models.append(FALLBACK_TTS_MODEL)
    return models


def _safe_error_message(body: Any) -> str:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:180]
        if isinstance(body.get("message"), str):
            return body["message"][:180]
    return "Gemini request failed"


def _build_reply_prompt(question: str, advisory: AdvisoryData) -> str:
    return f"""
You are AssetIQ, a Mercedes repair-versus-trade-in voice advisor.
You may respond naturally to greetings, thanks, and short follow-up questions, but only in the context of the current advisory data.

Answer only from this advisory data:
- current_value_rm: {advisory.current_value_rm}
- estimated_repair_cost_rm: {advisory.estimated_repair_cost_rm}
- predicted_value_after_repair_rm: {advisory.predicted_value_after_repair_rm}
- repair_outcome_rm: {advisory.repair_outcome_rm}
- trade_in_now_rm: {advisory.trade_in_now_rm}
- recommendation: {advisory.recommendation}
- summary: {advisory.summary}

Rules:
- Do not invent values, repairs, prices, appointments, or booking details.
- If the user asks for anything unrelated to the repair-versus-trade-in advisory, reply exactly:
  "{OUTSIDE_ADVISORY_REPLY}"
- Keep the answer short and natural for spoken output.
- Use one or two sentences. Do not produce long paragraphs.
- Mention only values present in the advisory data.

User question: {question}
""".strip()


def _clean_reply(reply: str, question: str, advisory: AdvisoryData) -> str:
    cleaned = " ".join(reply.split())
    if not cleaned:
        return fallback_reply(question, advisory)
    if conversation_reply(question, advisory):
        return cleaned[:500]
    if not is_advisory_question(question) and cleaned != OUTSIDE_ADVISORY_REPLY:
        return OUTSIDE_ADVISORY_REPLY
    return cleaned[:500]


def _create_interaction(api_key: str, payload: dict[str, Any], timeout_seconds: float = 20) -> dict[str, Any]:
    response = httpx.post(
        GEMINI_INTERACTIONS_URL,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=timeout_seconds,
    )
    logger.warning("Gemini interaction status_code=%s model=%s", response.status_code, payload.get("model"))
    try:
        body = response.json()
    except ValueError as exc:
        logger.warning("Gemini response JSON parsing failed: %s", exc)
        raise GeminiRequestError(response.status_code, "invalid Gemini JSON response") from exc

    if response.is_error:
        message = _safe_error_message(body)
        logger.warning("Gemini interaction failed status_code=%s error=%s", response.status_code, message)
        raise GeminiRequestError(response.status_code, message)

    return body


def _generate_reply(api_key: str, question: str, advisory: AdvisoryData) -> str:
    interaction = _create_interaction(
        api_key,
        {
            "model": TEXT_MODEL,
            "input": _build_reply_prompt(question, advisory),
        },
    )
    raw_text = _extract_output_text(interaction)
    return _clean_reply(raw_text, question, advisory)


def _extract_output_text(interaction: dict[str, Any]) -> str:
    output_text = interaction.get("output_text") or interaction.get("outputText")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    nested_text = _find_nested_text(interaction)
    if nested_text:
        return nested_text

    logger.warning(
        "Gemini text missing; top_level_keys=%s steps=%s preview=%s",
        sorted(interaction.keys()),
        _summarize_steps(interaction),
        _safe_response_preview(interaction),
    )
    return ""


def _find_nested_text(value: Any, path: tuple[str, ...] = ()) -> str | None:
    if isinstance(value, dict):
        for key in ("text", "output_text", "outputText"):
            text = value.get(key)
            if isinstance(text, str) and text.strip() and not _looks_like_prompt_path(path):
                logger.warning("Gemini text found at path=%s.%s length=%s", ".".join(path), key, len(text))
                return text

        for key, child in value.items():
            found = _find_nested_text(child, (*path, str(key)))
            if found:
                return found

    if isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_nested_text(child, (*path, str(index)))
            if found:
                return found

    if isinstance(value, str) and value.strip() and _looks_like_text_response_path(path):
        logger.warning("Gemini text found at path=%s length=%s", ".".join(path), len(value))
        return value

    return None


def _looks_like_prompt_path(path: tuple[str, ...]) -> bool:
    path_text = ".".join(path).lower()
    return "input" in path_text or "prompt" in path_text


def _looks_like_text_response_path(path: tuple[str, ...]) -> bool:
    path_text = ".".join(path).lower()
    if _looks_like_prompt_path(path):
        return False
    return any(part in path_text for part in ("content", "output", "response", "message"))


def _safe_response_preview(value: Any) -> str:
    def scrub(node: Any) -> Any:
        if isinstance(node, dict):
            return {str(key): scrub(child) for key, child in list(node.items())[:20]}
        if isinstance(node, list):
            return [scrub(child) for child in node[:6]]
        if isinstance(node, str):
            return "<omitted base64/data>" if len(node) > 240 else node
        return node

    try:
        return json.dumps(scrub(value), ensure_ascii=True)[:1000]
    except TypeError:
        return repr(value)[:1000]


def _extract_output_audio_data(interaction: dict[str, Any]) -> str:
    output_audio = interaction.get("output_audio") or interaction.get("outputAudio")
    data = output_audio.get("data") if isinstance(output_audio, dict) else None
    if isinstance(data, str) and data:
        return data

    nested_data = _find_nested_audio_data(interaction)
    if nested_data:
        return nested_data

    logger.warning(
        "Gemini TTS audio missing; top_level_keys=%s output_audio_type=%s steps=%s",
        sorted(interaction.keys()),
        type(output_audio).__name__,
        _summarize_steps(interaction),
    )
    raise ValueError("audio data missing from Gemini TTS response")


def _find_nested_audio_data(value: Any, path: tuple[str, ...] = ()) -> str | None:
    if isinstance(value, dict):
        value_type = str(value.get("type") or value.get("content_type") or value.get("contentType") or "").lower()
        data = value.get("data")
        path_text = ".".join(path).lower()
        if isinstance(data, str) and data and ("audio" in path_text or value_type == "audio"):
            logger.warning("Gemini TTS audio found at path=%s length=%s", ".".join(path), len(data))
            return data

        for key, child in value.items():
            found = _find_nested_audio_data(child, (*path, str(key)))
            if found:
                return found

    if isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_nested_audio_data(child, (*path, str(index)))
            if found:
                return found

    return None


def _summarize_steps(interaction: dict[str, Any]) -> list[dict[str, Any]]:
    steps = interaction.get("steps")
    if not isinstance(steps, list):
        return []

    summary = []
    for step in steps[:8]:
        if not isinstance(step, dict):
            summary.append({"type": type(step).__name__})
            continue
        summary.append(
            {
                "keys": sorted(step.keys()),
                "type": step.get("type") or step.get("step_type") or step.get("stepType"),
                "has_audio": _has_audio_key(step),
                "has_text": _has_text_key(step),
            }
        )
    return summary


def _has_audio_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any("audio" in str(key).lower() or _has_audio_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_has_audio_key(child) for child in value)
    return False


def _has_text_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any("text" in str(key).lower() or _has_text_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_has_text_key(child) for child in value)
    return False


def _pcm_base64_to_wav_base64(pcm_base64: str) -> str:
    pcm = base64.b64decode(pcm_base64)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(pcm)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _generate_audio(api_key: str, reply: str) -> TtsAudio:
    global _tts_quota_exhausted

    cached = _tts_audio_cache.get(reply)
    if cached:
        return cached

    if _tts_quota_exhausted:
        raise GeminiTtsQuotaExceeded()

    quota_failures = 0
    models = _tts_models()
    for model in models:
        try:
            interaction = _create_interaction(
                api_key,
                {
                    "model": model,
                    "input": f"Say in a calm, premium assistant voice: {reply}",
                    "response_format": {"type": "audio"},
                    "generation_config": {"speech_config": [{"voice": VOICE_NAME}]},
                },
                timeout_seconds=TTS_TIMEOUT_SECONDS,
            )
            pcm_base64 = _extract_output_audio_data(interaction)
            audio = TtsAudio(audio_base64=_pcm_base64_to_wav_base64(pcm_base64))
            _tts_audio_cache[reply] = audio
            return audio
        except httpx.TimeoutException as exc:
            logger.warning("Gemini TTS timed out for model=%s after %.1fs", model, TTS_TIMEOUT_SECONDS)
            raise GeminiTtsTimeout() from exc
        except GeminiRequestError as exc:
            if exc.status_code == 429:
                quota_failures += 1
                logger.warning("Gemini TTS quota exceeded for model=%s; trying fallback if available", model)
                continue
            raise
        except Exception as exc:
            logger.warning("Gemini TTS audio parsing failed for model=%s: %s", model, exc)
            raise

    if quota_failures == len(models):
        _tts_quota_exhausted = True
        raise GeminiTtsQuotaExceeded()

    raise GeminiRequestError(None, "Gemini TTS request failed")


class AdvisoryVoiceService:
    def respond(self, question: str, advisory: AdvisoryData) -> AdvisoryVoiceResponse:
        api_key = _api_key()
        gemini_key_detected = api_key is not None
        logger.warning("Gemini API key detected=%s", gemini_key_detected)
        reply = fast_local_reply(question, advisory) or ""
        text_provider = "local" if reply else "gemini"

        if api_key is None:
            return AdvisoryVoiceResponse(
                reply=reply or fallback_reply(question, advisory),
                tts_provider="gemini-unavailable",
                fallback_reason="missing_gemini_api_key",
                text_provider="local",
                gemini_key_detected=False,
            )

        if not reply:
            try:
                reply = _generate_reply(api_key, question, advisory)
            except GeminiRequestError as exc:
                logger.warning("Gemini reply generation failed: %s", exc.message)
                reply = fallback_reply(question, advisory)
                text_provider = "local"
            except Exception as exc:
                logger.warning("Gemini reply generation failed: %s", exc)
                reply = fallback_reply(question, advisory)
                text_provider = "local"

        try:
            tts_started_at = time.perf_counter()
            audio = _generate_audio(api_key, reply)
            tts_wait_ms = round((time.perf_counter() - tts_started_at) * 1000)
            return AdvisoryVoiceResponse(
                reply=reply,
                audio_base64=audio.audio_base64,
                mime_type=audio.mime_type,
                tts_provider="gemini",
                fallback_reason=None,
                text_provider=text_provider,
                tts_wait_ms=tts_wait_ms,
                gemini_key_detected=True,
            )
        except GeminiTtsTimeout:
            fallback_reason = "gemini_tts_timeout"
            logger.warning("Gemini TTS failed reason=%s", fallback_reason)
        except GeminiTtsQuotaExceeded:
            fallback_reason = "gemini_tts_quota_exceeded"
            logger.warning("Gemini TTS failed reason=%s", fallback_reason)
        except GeminiRequestError as exc:
            fallback_reason = f"gemini_http_{exc.status_code}" if exc.status_code else "gemini_request_failed"
            logger.warning("Gemini TTS failed reason=%s error=%s", fallback_reason, exc.message)
        except Exception as exc:
            fallback_reason = "gemini_audio_missing"
            logger.warning("Gemini TTS failed reason=%s error=%s", fallback_reason, exc)

        tts_wait_ms = round((time.perf_counter() - tts_started_at) * 1000)
        return AdvisoryVoiceResponse(
            reply=reply,
            audio_base64=None,
            mime_type=None,
            tts_provider="gemini-unavailable",
            fallback_reason=fallback_reason,
            text_provider=text_provider,
            tts_wait_ms=tts_wait_ms,
            gemini_key_detected=True,
        )
