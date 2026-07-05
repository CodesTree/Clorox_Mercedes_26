"""Calendar reasoning for the booking agent.

- classify_reply: interpret the workshop's Telegram reply (Gemini, with a
  deterministic keyword fallback).
- find_next_available_slot: pick the next free working-hours slot from Google
  Calendar FreeBusy (with a deterministic fallback).
- create_calendar_event: write the confirmed event via the service account.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Literal

from app import orm
from app.config import get_settings
from app.services.google_calendar import (
    WORKING_END_HOUR,
    WORKING_START_HOUR,
    GoogleCalendarService,
    google_calendar_service,
)

logger = logging.getLogger(__name__)

Intent = Literal["confirmed", "unavailable", "unclear"]

GEMINI_MODEL_FALLBACKS = ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash")

MAX_SEARCH_DAYS = 14

_UNAVAILABLE_PHRASES = (
    "not available",
    "no slot",
    "fully booked",
    "another time",
    "different time",
    "can not",
)
_UNAVAILABLE_TOKENS = {
    "unavailable",
    "taken",
    "full",
    "busy",
    "cannot",
    "cant",
    "reschedule",
    "unfortunately",
    "no",
}
_CONFIRM_TOKENS = {
    "confirm",
    "confirmed",
    "yes",
    "ok",
    "okay",
    "approved",
    "available",
    "book",
    "booked",
    "sure",
    "great",
}


# --- reply classification ----------------------------------------------------

def _keyword_classify(text: str) -> Intent:
    lowered = text.strip().casefold()
    if not lowered:
        return "unclear"

    if any(phrase in lowered for phrase in _UNAVAILABLE_PHRASES):
        return "unavailable"

    tokens = set(re.findall(r"[a-z']+", lowered.replace("'", "")))
    if tokens & _UNAVAILABLE_TOKENS:
        return "unavailable"
    if tokens & _CONFIRM_TOKENS:
        return "confirmed"
    return "unclear"


def _parse_intent(raw: str) -> Intent | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            line for line in cleaned.splitlines() if not line.startswith("```")
        ).strip()

    intent = ""
    try:
        data = json.loads(cleaned)
        intent = str(data.get("intent", "")).strip().lower()
    except (json.JSONDecodeError, AttributeError):
        intent = cleaned.lower()

    if intent in ("confirmed", "unavailable", "unclear"):
        return intent  # type: ignore[return-value]
    return None


def _gemini_classify(text: str, booking: orm.Booking, settings) -> Intent | None:
    try:
        from google import genai
    except ImportError:
        return None

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
    except Exception:
        logger.exception("Gemini client init failed")
        return None

    prompt = (
        "You classify a car workshop's reply to an appointment proposal.\n"
        'Return strict JSON only: {"intent": "confirmed" | "unavailable" | "unclear"}.\n'
        "confirmed = the proposed slot is accepted/booked.\n"
        "unavailable = the proposed slot cannot be honoured / another time is needed.\n"
        "unclear = anything else.\n\n"
        f"Proposed date {booking.date} at {booking.time}.\n"
        f"Reply: {text}"
    )

    last_error: Exception | None = None
    for model_id in GEMINI_MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(model=model_id, contents=prompt)
            intent = _parse_intent(getattr(response, "text", None) or "")
            if intent is not None:
                return intent
        except Exception as exc:  # network/model errors are environment-specific
            last_error = exc

    if last_error is not None:
        logger.warning("Gemini classification failed: %s", last_error)
    return None


def classify_reply(text: str, booking: orm.Booking) -> Intent:
    settings = get_settings()
    if settings.gemini_api_key.strip():
        intent = _gemini_classify(text, booking, settings)
        if intent is not None:
            return intent
    return _keyword_classify(text)


# --- availability search -----------------------------------------------------

def _deterministic_next(current: datetime) -> tuple[str, str]:
    candidate = current + timedelta(hours=1)
    if candidate.hour < WORKING_START_HOUR:
        candidate = candidate.replace(hour=WORKING_START_HOUR, minute=0)
    if candidate.hour >= WORKING_END_HOUR:
        candidate = (candidate + timedelta(days=1)).replace(
            hour=WORKING_START_HOUR, minute=0
        )
    return candidate.date().isoformat(), candidate.strftime("%H:%M")


def find_next_available_slot(
    after_date: str,
    after_time: str,
    service: GoogleCalendarService | None = None,
) -> tuple[str, str]:
    service = service or google_calendar_service
    tzinfo = service._resolve_tzinfo()

    try:
        current = datetime.fromisoformat(f"{after_date}T{after_time}:00").replace(
            tzinfo=tzinfo
        )
    except ValueError:
        current = datetime.now(tzinfo)

    for day_offset in range(MAX_SEARCH_DAYS):
        day = (current + timedelta(days=day_offset)).date().isoformat()
        for slot in service.free_slots_for_date(day):
            slot_dt = datetime.fromisoformat(f"{day}T{slot}:00").replace(tzinfo=tzinfo)
            if slot_dt > current:
                return day, slot

    return _deterministic_next(current)


# --- event creation ----------------------------------------------------------

def create_calendar_event(
    booking: orm.Booking, service: GoogleCalendarService | None = None
) -> str:
    service = service or google_calendar_service
    result = service.create_booking_event(booking)
    return result.event_id
