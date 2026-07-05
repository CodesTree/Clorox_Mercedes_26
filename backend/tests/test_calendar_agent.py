from datetime import timedelta, timezone
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services import calendar_agent
from app.services.google_calendar import CalendarEventResult, GoogleCalendarService


def _booking(**overrides):
    data = dict(
        name="Chan",
        workshop="Hap Seng Star KL",
        car_model="C-Class",
        purpose="Certified inspection",
        date="2026-07-10",
        time="10:00",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.fixture(autouse=True)
def _no_gemini(monkeypatch):
    # Force the deterministic keyword path for classify tests.
    monkeypatch.setattr(
        calendar_agent, "get_settings", lambda: SimpleNamespace(gemini_api_key="")
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("CONFIRM", "confirmed"),
        ("Yes, that works", "confirmed"),
        ("ok booked", "confirmed"),
        ("That slot is taken", "unavailable"),
        ("Sorry, not available", "unavailable"),
        ("We're fully booked", "unavailable"),
        ("no", "unavailable"),
        ("Maybe later", "unclear"),
        ("", "unclear"),
    ],
)
def test_keyword_classify(text, expected):
    assert calendar_agent.classify_reply(text, _booking()) == expected


def test_find_next_available_slot_same_day_fallback():
    # Unconfigured service account -> free_slots_for_date falls back to all slots.
    service = GoogleCalendarService(
        settings=Settings(
            google_calendar_credentials_json="",
            google_calendar_id="primary",
            google_calendar_timezone="Asia/Kuala_Lumpur",
        )
    )
    date, time = calendar_agent.find_next_available_slot(
        "2026-07-10", "10:00", service=service
    )
    assert (date, time) == ("2026-07-10", "11:00")


def test_find_next_available_slot_skips_full_day():
    slots = {"2026-07-10": [], "2026-07-11": ["09:00", "10:00"]}
    fake = SimpleNamespace(
        _resolve_tzinfo=lambda: timezone(timedelta(hours=8)),
        free_slots_for_date=lambda day: slots.get(day, []),
    )
    date, time = calendar_agent.find_next_available_slot(
        "2026-07-10", "16:00", service=fake
    )
    assert (date, time) == ("2026-07-11", "09:00")


def test_create_calendar_event_delegates_to_service():
    fake = SimpleNamespace(
        create_booking_event=lambda booking: CalendarEventResult(event_id="evt-42")
    )
    assert calendar_agent.create_calendar_event(_booking(), service=fake) == "evt-42"
