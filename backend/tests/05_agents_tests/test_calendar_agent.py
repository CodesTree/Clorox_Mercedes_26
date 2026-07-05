from types import SimpleNamespace

from app.services import calendar_agent
from app.services.calendar_agent import build_event_payload, resolve_booking
from datetime import datetime
#from dateutil.parser import parse


def test_build_event_payload_creates_calendar_body():
    booking = SimpleNamespace(
        name="Aisha Rahman",
        workshop="Mercedes PJ",
        car_model="C-Class",
        purpose="Inspection",
        date="2026-07-10",
        time="09:30",
    )

    payload = build_event_payload(booking)

    assert payload["summary"] == "Mercedes Inspection — C-Class"
    assert payload["description"] == "Purpose: Inspection\nName: Aisha Rahman"
    assert payload["location"] == "Mercedes PJ"
    assert payload["start"]["dateTime"] == "2026-07-10T09:30:00+08:00"
    assert payload["start"]["timeZone"] == "Asia/Kuala_Lumpur"
    assert payload["end"]["dateTime"] == "2026-07-10T10:30:00+08:00"
    assert payload["end"]["timeZone"] == "Asia/Kuala_Lumpur"

    start = datetime.fromisoformat(payload["start"]["dateTime"])
    end = datetime.fromisoformat(payload["end"]["dateTime"])

    assert (end - start).total_seconds() == 3600
    
    assert payload["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "email", "minutes": 60}],
    }


def _settings(**overrides):
    values = {
        "google_calendar_credentials_json": "",
        "google_calendar_id": "",
        "gemini_api_key": "",
        "model_fields_set": set(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_resolve_booking_dry_run_without_google_keys(monkeypatch):
    booking = SimpleNamespace(
        name="Aisha Rahman",
        workshop="Mercedes PJ",
        car_model="C-Class",
        purpose="Inspection",
        date="2026-07-10",
        time="09:30",
    )
    settings = _settings()
    payload = {"summary": "dry-run payload"}
    logged = {}

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: settings)
    monkeypatch.setattr(calendar_agent, "build_event_payload", lambda value: payload)
    monkeypatch.setattr(calendar_agent.logger, "info", lambda message, value: logged.setdefault("payload", value))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("calendar API should not be called in dry-run mode")

    monkeypatch.setattr(calendar_agent, "_create_calendar_event", fail_if_called)

    result = resolve_booking(booking)

    assert result == {"status": "dry_run", "calendar_event_id": None, "dry_run": True}
    assert logged["payload"] == payload


def test_resolve_booking_deterministic_path_without_gemini(monkeypatch):
    booking = SimpleNamespace(
        name="Aisha Rahman",
        workshop="Mercedes PJ",
        car_model="C-Class",
        purpose="Inspection",
        date="2026-07-10",
        time="09:30",
    )
    settings = _settings(
        google_calendar_credentials_json="service-account.json",
        google_calendar_id="calendar-id",
        model_fields_set={"google_calendar_credentials_json", "google_calendar_id"},
    )
    payload = {"summary": "deterministic payload"}
    captured = {}

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: settings)
    monkeypatch.setattr(calendar_agent, "build_event_payload", lambda value: payload)
    monkeypatch.setattr(calendar_agent, "_extract_booking_via_gemini", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("gemini should not run")))
    monkeypatch.setattr(
        calendar_agent,
        "_create_calendar_event",
        lambda value, value_settings: captured.update({"payload": value}) or {"status": "booked", "calendar_event_id": "evt-123", "dry_run": False},
    )

    result = resolve_booking(booking)

    assert result == {"status": "booked", "calendar_event_id": "evt-123", "dry_run": False}
    assert captured["payload"] == payload


def test_resolve_booking_gemini_ambiguous_falls_back(monkeypatch):
    booking = SimpleNamespace(
        name="Aisha Rahman",
        workshop="Mercedes PJ",
        car_model="C-Class",
        purpose="Inspection",
        date="2026-07-10",
        time="09:30",
        confirmation_text="not sure",
    )
    settings = _settings(
        google_calendar_credentials_json="service-account.json",
        google_calendar_id="calendar-id",
        gemini_api_key="gemini-key",
        model_fields_set={
            "google_calendar_credentials_json",
            "google_calendar_id",
            "gemini_api_key",
        },
    )
    raw_payload = {"summary": "raw payload"}
    created = {}

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: settings)
    monkeypatch.setattr(calendar_agent, "_extract_booking_via_gemini", lambda *args, **kwargs: None)
    monkeypatch.setattr(calendar_agent, "build_event_payload", lambda value: raw_payload)
    monkeypatch.setattr(
        calendar_agent,
        "_create_calendar_event",
        lambda value, value_settings: created.update({"payload": value}) or {"status": "booked", "calendar_event_id": "evt-456", "dry_run": False},
    )

    result = resolve_booking(booking)

    assert result == {"status": "booked", "calendar_event_id": "evt-456", "dry_run": False}
    assert created["payload"] == raw_payload


def test_resolve_booking_gemini_exception_falls_back(monkeypatch):
    booking = SimpleNamespace(
        name="Aisha Rahman",
        workshop="Mercedes PJ",
        car_model="C-Class",
        purpose="Inspection",
        date="2026-07-10",
        time="09:30",
        confirmation_text="confirmed",
    )
    settings = _settings(
        google_calendar_credentials_json="service-account.json",
        google_calendar_id="calendar-id",
        gemini_api_key="gemini-key",
        model_fields_set={
            "google_calendar_credentials_json",
            "google_calendar_id",
            "gemini_api_key",
        },
    )
    payload = {"summary": "raw payload"}
    created = {}

    def raise_gemini(*args, **kwargs):
        raise RuntimeError("gemini failure")

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: settings)
    monkeypatch.setattr(calendar_agent, "_extract_booking_via_gemini", raise_gemini)
    monkeypatch.setattr(calendar_agent, "build_event_payload", lambda value: payload)
    monkeypatch.setattr(
        calendar_agent,
        "_create_calendar_event",
        lambda value, value_settings: created.update({"payload": value}) or {"status": "booked", "calendar_event_id": "evt-789", "dry_run": False},
    )

    result = resolve_booking(booking)

    assert result == {"status": "booked", "calendar_event_id": "evt-789", "dry_run": False}
    assert created["payload"] == payload

    