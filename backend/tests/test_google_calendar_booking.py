from app import orm
from app.config import Settings
from app.db import SessionLocal
from app.schemas import BookingIn
from app.services.booking import SharedCalendarDispatcher, create_booking
from app.services.google_calendar import GoogleCalendarService


BOOKING_PAYLOAD = {
    "profile_id": 1,
    "name": "Chan",
    "workshop": "Hap Seng Star KL",
    "car_model": "Mercedes-AMG GT 63 S 4MATIC+",
    "purpose": "Certified inspection",
    "date": "2026-07-10",
    "time": "10:00",
}


def service_account_settings() -> Settings:
    return Settings(
        google_calendar_credentials_json='{"type":"service_account"}',
        google_calendar_id="primary",
        google_calendar_timezone="Asia/Kuala_Lumpur",
    )


def test_booking_event_payload_uses_shared_calendar_shape_and_local_time():
    service = GoogleCalendarService(settings=service_account_settings())
    row = orm.Booking(**BOOKING_PAYLOAD, status="pending")

    event = service.build_booking_event(row)

    assert event["summary"] == "AssetIQ Certified Inspection - Mercedes-AMG GT 63 S 4MATIC+"
    assert event["location"] == "Hap Seng Star KL"
    assert event["description"] == (
        "Purpose: Certified inspection\n"
        "Name: Chan\n"
        "Booked through AssetIQ for Mercedes-Benz."
    )
    assert event["start"] == {
        "dateTime": "2026-07-10T10:00:00+08:00",
        "timeZone": "Asia/Kuala_Lumpur",
    }
    assert event["end"] == {
        "dateTime": "2026-07-10T11:00:00+08:00",
        "timeZone": "Asia/Kuala_Lumpur",
    }


# NOTE: SharedCalendarDispatcher is not wired to the /booking endpoint. The
# endpoint uses the Telegram-confirmation flow (see app.services.telegram_bot
# and tests/05_agents_tests/test_booking_route.py); calendar events are only
# created after confirmation, via app.services.calendar_agent.resolve_booking,
# which reuses GoogleCalendarService.insert_event. These tests exercise the
# SharedCalendarDispatcher/create_booking service pair directly.


def test_booking_stays_dry_run_when_shared_calendar_is_not_configured():
    service = GoogleCalendarService(
        settings=Settings(
            google_calendar_credentials_json="",
            google_calendar_id="",
        )
    )
    dispatcher = SharedCalendarDispatcher(service)

    with SessionLocal() as session:
        result = create_booking(
            session=session, booking_in=BookingIn(**BOOKING_PAYLOAD), dispatcher=dispatcher
        )

    assert result.status == "dry_run"
    assert result.dispatched is False
    assert result.dry_run is True
    assert result.payload["calendar_mode"] == "shared"
    assert "auth_url" not in result.payload


def test_booking_falls_back_to_dry_run_when_calendar_api_fails():
    def failing_event_inserter(calendar_id, event):
        raise RuntimeError("calendar network failed")

    service = GoogleCalendarService(
        settings=service_account_settings(),
        event_inserter=failing_event_inserter,
    )
    dispatcher = SharedCalendarDispatcher(service)

    with SessionLocal() as session:
        result = create_booking(
            session=session, booking_in=BookingIn(**BOOKING_PAYLOAD), dispatcher=dispatcher
        )

    assert result.status == "dry_run"
    assert result.dispatched is False
    assert result.dry_run is True
    assert result.payload["calendar_mode"] == "shared"
    assert "calendar network failed" in result.payload["calendar_error"]


def test_booking_creates_shared_calendar_event_when_configured():
    inserted_events = []

    def fake_event_inserter(calendar_id, event):
        inserted_events.append((calendar_id, event))
        return {"id": "shared-event-123", "htmlLink": "https://calendar.google.test/event/123"}

    service = GoogleCalendarService(
        settings=service_account_settings(),
        event_inserter=fake_event_inserter,
    )
    dispatcher = SharedCalendarDispatcher(service)

    with SessionLocal() as session:
        result = create_booking(
            session=session, booking_in=BookingIn(**BOOKING_PAYLOAD), dispatcher=dispatcher
        )

    assert result.status == "booked"
    assert result.dispatched is True
    assert result.dry_run is False
    assert result.payload["calendar_mode"] == "shared"
    assert result.payload["calendar_event_id"] == "shared-event-123"
    assert result.payload["calendar_html_link"] == "https://calendar.google.test/event/123"
    assert inserted_events[0][0] == "primary"
    assert inserted_events[0][1]["summary"].startswith("AssetIQ Certified Inspection")

    with SessionLocal() as session:
        row = session.get(orm.Booking, result.booking_id)
        assert row is not None
        assert row.status == "booked"
        assert row.calendar_event_id == "shared-event-123"
