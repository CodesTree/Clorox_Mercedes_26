from __future__ import annotations

import json
import logging
import sys
from types import ModuleType, SimpleNamespace

from app.services import calendar_agent, telegram_bot
from app.services.calendar_agent import build_event_payload, resolve_booking


def _booking(**overrides):
    values = {
        "name": "Aisha Rahman",
        "workshop": "Mercedes PJ",
        "car_model": "C-Class",
        "purpose": "Inspection",
        "date": "2026-07-10",
        "time": "09:30",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _settings(**overrides):
    values = {
        "google_calendar_credentials_json": "",
        "google_calendar_id": "",
        "gemini_api_key": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "model_fields_set": set(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_event_payload_creates_calendar_body():
    payload = build_event_payload(_booking())

    assert payload["summary"] == "Mercedes Inspection — C-Class"
    assert payload["description"] == "Purpose: Inspection\nName: Aisha Rahman"
    assert payload["location"] == "Mercedes PJ"
    assert payload["start"]["dateTime"] == "2026-07-10T09:30:00+08:00"
    assert payload["start"]["timeZone"] == "Asia/Kuala_Lumpur"
    assert payload["end"]["dateTime"] == "2026-07-10T10:30:00+08:00"
    assert payload["end"]["timeZone"] == "Asia/Kuala_Lumpur"
    assert payload["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "email", "minutes": 60}],
    }


def test_resolve_booking_gemini_path_uses_extracted_fields_and_books(monkeypatch):
    booking = _booking(
        workshop="Raw workshop",
        car_model="Raw model",
        purpose="Raw purpose",
        confirmation_text="confirmed",
    )
    settings = _settings(
        google_calendar_credentials_json='{"client_email":"svc@example.com"}',
        google_calendar_id="calendar-id",
        gemini_api_key="gemini-key",
        model_fields_set={
            "google_calendar_credentials_json",
            "google_calendar_id",
            "gemini_api_key",
        },
    )
    extracted = {
        "workshop": "Gemini workshop",
        "car_model": "Gemini C-Class",
        "purpose": "Gemini inspection",
        "date": "2026-07-11",
        "time": "11:15",
    }
    captured = {}

    fake_google = ModuleType("google")
    fake_google.__path__ = []
    fake_genai = ModuleType("google.generativeai")

    class FakeModel:
        def generate_content(self, prompt):
            captured["prompt"] = prompt
            return SimpleNamespace(text=json.dumps({**extracted, "ambiguous": False}))

    def fake_configure(api_key):
        captured["api_key"] = api_key

    def fake_model_factory(model_id):
        captured["model_id"] = model_id
        return FakeModel()

    fake_genai.configure = fake_configure
    fake_genai.GenerativeModel = fake_model_factory
    fake_google.generativeai = fake_genai

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: settings)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    def fake_create_calendar_event(payload, service_settings):
        captured["payload"] = payload
        captured["service_settings"] = service_settings
        return {"status": "booked", "calendar_event_id": "evt-123", "dry_run": False}

    monkeypatch.setattr(calendar_agent, "_create_calendar_event", fake_create_calendar_event)

    result = resolve_booking(booking)

    assert result == {"status": "booked", "calendar_event_id": "evt-123", "dry_run": False}
    assert captured["api_key"] == "gemini-key"
    assert captured["model_id"] == calendar_agent.GEMINI_MODEL_ID
    assert captured["payload"] == build_event_payload(_booking(**extracted))


def test_resolve_booking_deterministic_fallback_builds_same_event_shape_from_structured_data(monkeypatch):
    booking = _booking()
    settings = _settings(
        google_calendar_credentials_json="service-account.json",
        google_calendar_id="calendar-id",
        model_fields_set={"google_calendar_credentials_json", "google_calendar_id"},
    )
    captured = {}

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: settings)
    monkeypatch.setattr(
        calendar_agent,
        "_extract_booking_via_gemini",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("gemini should not run")),
    )

    def fake_create_calendar_event(payload, service_settings):
        captured["payload"] = payload
        return {"status": "booked", "calendar_event_id": "evt-456", "dry_run": False}

    monkeypatch.setattr(calendar_agent, "_create_calendar_event", fake_create_calendar_event)

    result = resolve_booking(booking)

    assert result == {"status": "booked", "calendar_event_id": "evt-456", "dry_run": False}
    assert captured["payload"] == build_event_payload(booking)


def test_resolve_booking_dry_run_makes_no_external_call_and_returns_dry_run(monkeypatch, caplog):
    booking = _booking()
    settings = _settings()

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: settings)
    monkeypatch.setattr(
        calendar_agent,
        "_create_calendar_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("calendar API should not be called")),
    )
    monkeypatch.setattr(
        calendar_agent,
        "_extract_booking_via_gemini",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("gemini should not run")),
    )

    with caplog.at_level(logging.INFO):
        result = resolve_booking(booking)

    payload = build_event_payload(booking)
    assert result == {"status": "dry_run", "calendar_event_id": None, "dry_run": True}
    assert any(str(payload) in record.message for record in caplog.records)
    assert "dry-run" in caplog.text
    assert "Calendar dry-run payload:" in caplog.text


def test_no_secret_strings_leak_in_logs_or_return_values(monkeypatch, caplog):
    telegram_secret = "TELEGRAM_BOT_TOKEN=telegram-secret-value"
    gemini_secret = "GEMINI_API_KEY=gemini-secret-value"
    credentials_secret = '{"private_key":"credentials-secret-value"}'

    telegram_settings = _settings(
        telegram_bot_token=telegram_secret,
        telegram_chat_id="telegram-chat-secret",
        model_fields_set={"telegram_bot_token", "telegram_chat_id"},
    )
    calendar_settings = _settings(
        google_calendar_credentials_json=credentials_secret,
        google_calendar_id="calendar-secret",
        gemini_api_key=gemini_secret,
        model_fields_set={
            "google_calendar_credentials_json",
            "google_calendar_id",
            "gemini_api_key",
        },
    )

    outputs = []

    monkeypatch.setattr(telegram_bot, "get_settings", lambda: telegram_settings)
    monkeypatch.setattr(
        telegram_bot.httpx,
        "get",
        lambda url, params=None, timeout=None: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "ok": True,
                "result": [
                    {
                        "update_id": 7,
                        "message": {
                            "chat": {"id": "telegram-chat-secret"},
                            "text": "confirmed",
                        },
                    }
                ],
            },
        ),
    )
    outputs.append(telegram_bot.format_booking_message(_booking()))
    outputs.append(telegram_bot.is_confirmation("confirmed"))
    outputs.append(telegram_bot.poll_for_confirmation("telegram-chat-secret", 0))

    monkeypatch.setattr(calendar_agent, "get_settings", lambda: calendar_settings)
    monkeypatch.setattr(
        calendar_agent,
        "_create_calendar_event",
        lambda payload, settings: {"status": "booked", "calendar_event_id": "evt-secret", "dry_run": False},
    )

    fake_google = ModuleType("google")
    fake_google.__path__ = []
    fake_genai = ModuleType("google.generativeai")

    class FakeModel:
        def generate_content(self, prompt):
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "workshop": "Gemini workshop",
                        "car_model": "Gemini C-Class",
                        "purpose": "Gemini inspection",
                        "date": "2026-07-11",
                        "time": "11:15",
                        "ambiguous": False,
                    }
                )
            )

    fake_genai.configure = lambda api_key: None
    fake_genai.GenerativeModel = lambda model_id: FakeModel()
    fake_google.generativeai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    with caplog.at_level(logging.INFO):
        outputs.append(calendar_agent.build_event_payload(_booking()))
        outputs.append(calendar_agent.resolve_booking(_booking(confirmation_text="confirmed")))

    combined = caplog.text + "\n" + "\n".join(repr(value) for value in outputs)

    for secret in (telegram_secret, gemini_secret, credentials_secret):
        assert secret not in combined