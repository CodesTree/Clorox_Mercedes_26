from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from ..config import get_settings
from .dispatcher import BookingRecord
from .google_calendar import GoogleCalendarService


logger = logging.getLogger(__name__)

GEMINI_MODEL_ID = "gemini-2.5-flash"
GEMINI_MODEL_FALLBACKS = (
    GEMINI_MODEL_ID,
    "gemini-2.0-flash",
    "gemini-1.5-flash",
)
_BOOKING_FIELDS = ("name", "workshop", "car_model", "purpose", "date", "time")


def build_event_payload(booking: BookingRecord) -> dict:
    kuala_lumpur_tz = timezone(timedelta(hours=8), name="Asia/Kuala_Lumpur")
    start = datetime.strptime(
        f"{booking.date} {booking.time}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=kuala_lumpur_tz)
    end = start + timedelta(hours=1)

    return {
        "summary": f"Mercedes Inspection — {booking.car_model}",
        "description": f"Purpose: {booking.purpose}\nName: {booking.name}",
        "location": booking.workshop,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "Asia/Kuala_Lumpur",
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "Asia/Kuala_Lumpur",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {
                    "method": "email",
                    "minutes": 60,
                }
            ],
        },
    }


def _booking_namespace(booking: BookingRecord, overrides: dict[str, str] | None = None) -> SimpleNamespace:
    data = {field: getattr(booking, field) for field in _BOOKING_FIELDS}
    if overrides:
        data.update(overrides)
    return SimpleNamespace(**data)


def _setting_is_configured(settings, field_name: str) -> bool:
    value = getattr(settings, field_name, "")
    if field_name not in getattr(settings, "model_fields_set", set()):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _dry_run_booking(booking: BookingRecord) -> dict:
    payload = build_event_payload(booking)
    logger.info("Calendar dry-run payload: %s", payload)
    return {"status": "dry_run", "calendar_event_id": None, "dry_run": True}


def _create_calendar_event(payload: dict, settings) -> dict:
    service = GoogleCalendarService(settings=settings)
    response = service.insert_event(settings.google_calendar_id, payload)
    event_id = response.get("id") if isinstance(response, dict) else None
    if not event_id:
        raise RuntimeError("Calendar API response missing event id")

    return {"status": "booked", "calendar_event_id": str(event_id), "dry_run": False}


def _clean_json_payload(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    return json.loads(cleaned)


def _extract_fields_from_response(response_text: str) -> dict | None:
    if not response_text:
        return None

    payload = _clean_json_payload(response_text)
    if payload.get("ambiguous") is True:
        return None

    required_fields = {"workshop", "car_model", "purpose", "date", "time"}
    if not required_fields.issubset(payload):
        return None

    return {field: str(payload[field]) for field in required_fields}


def _generate_gemini_response_text(prompt: str, settings) -> str:
    try:
        from google import genai
    except ImportError:
        genai = None

    if genai is not None:
        client = genai.Client(api_key=settings.gemini_api_key)
        last_error: Exception | None = None
        for model_id in GEMINI_MODEL_FALLBACKS:
            try:
                response = client.models.generate_content(model=model_id, contents=prompt)
                return getattr(response, "text", None) or ""
            except Exception as exc:  # pragma: no cover - network/client failures are environment-specific
                last_error = exc
        if last_error is not None:
            raise last_error

    try:
        from google import generativeai
    except ImportError as exc:  # pragma: no cover - exercised via mocks in tests
        if genai is None:
            raise RuntimeError("google-genai SDK unavailable. Run 'pip install google-genai'") from exc
        raise

    generativeai.configure(api_key=settings.gemini_api_key)
    last_error = None
    for model_id in GEMINI_MODEL_FALLBACKS:
        try:
            model = generativeai.GenerativeModel(model_id)
            response = model.generate_content(prompt)
            return getattr(response, "text", None) or ""
        except Exception as exc:  # pragma: no cover - network/client failures are environment-specific
            last_error = exc

    if last_error is not None:
        raise last_error

    return ""


def _extract_booking_via_gemini(booking: BookingRecord, settings) -> dict | None:
    confirmation_text = str(getattr(booking, "confirmation_text", "") or "")
    booking_context = json.dumps(
        {field: getattr(booking, field) for field in _BOOKING_FIELDS},
        ensure_ascii=False,
    )
    prompt = (
        "System: extract booking intent as JSON only. "
        'Return {"workshop", "car_model", "purpose", "date", "time", "ambiguous"}. '
        'Set "ambiguous": true if the confirmation text does not clearly match the booking.\n\n'
        f"Confirmation text: {confirmation_text}\n\n"
        f"Structured booking fields: {booking_context}"
    )

    response_text = _generate_gemini_response_text(prompt, settings)
    return _extract_fields_from_response(response_text)


def _deterministic_resolve(booking: BookingRecord, settings) -> dict:
    try:
        payload = build_event_payload(booking)
        return _create_calendar_event(payload, settings)
    except Exception:
        logger.exception("Deterministic calendar resolution failed; falling back to dry-run")
        return _dry_run_booking(booking)


def resolve_booking(booking: BookingRecord) -> dict:
    settings = get_settings()

    has_google = _setting_is_configured(settings, "google_calendar_credentials_json") and _setting_is_configured(
        settings, "google_calendar_id"
    )
    has_gemini = _setting_is_configured(settings, "gemini_api_key")

    if not has_google:
        return _dry_run_booking(booking)

    if not has_gemini:
        return _deterministic_resolve(booking, settings)

    try:
        extracted = _extract_booking_via_gemini(booking, settings)
    except Exception:
        logger.exception("Gemini booking extraction failed; falling back to deterministic resolution")
        return _deterministic_resolve(booking, settings)

    if extracted is None:
        return _deterministic_resolve(booking, settings)

    gemini_booking = _booking_namespace(booking, extracted)
    try:
        payload = build_event_payload(gemini_booking)
        return _create_calendar_event(payload, settings)
    except Exception:
        logger.exception("Gemini calendar creation failed; falling back to deterministic resolution")
        return _deterministic_resolve(booking, settings)