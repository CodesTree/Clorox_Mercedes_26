from fastapi.testclient import TestClient

from app import orm
from app.config import Settings
from app.db import SessionLocal
from app.main import app
from app.routers import booking
from app.services.booking import SharedCalendarDispatcher
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


def test_booking_stays_dry_run_when_shared_calendar_is_not_configured(monkeypatch):
    service = GoogleCalendarService(
        settings=Settings(
            google_calendar_credentials_json="",
            google_calendar_id="",
        )
    )
    monkeypatch.setattr(booking, "booking_dispatcher", SharedCalendarDispatcher(service))

    with TestClient(app) as client:
        resp = client.post("/booking", json=BOOKING_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["dispatched"] is False
    assert body["dry_run"] is True
    assert body["payload"]["calendar_mode"] == "shared"
    assert "auth_url" not in body["payload"]


def test_booking_falls_back_to_dry_run_when_calendar_api_fails(monkeypatch):
    def failing_event_inserter(calendar_id, event):
        raise RuntimeError("calendar network failed")

    service = GoogleCalendarService(
        settings=service_account_settings(),
        event_inserter=failing_event_inserter,
    )
    monkeypatch.setattr(booking, "booking_dispatcher", SharedCalendarDispatcher(service))

    with TestClient(app) as client:
        resp = client.post("/booking", json=BOOKING_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["dispatched"] is False
    assert body["dry_run"] is True
    assert body["payload"]["calendar_mode"] == "shared"
    assert "calendar network failed" in body["payload"]["calendar_error"]


def test_booking_reports_missing_service_account_file(monkeypatch, tmp_path):
    missing_credentials = tmp_path / "missing-google-sa.json"
    service = GoogleCalendarService(
        settings=Settings(
            google_calendar_credentials_json=str(missing_credentials),
            google_calendar_id="primary",
            google_calendar_timezone="Asia/Kuala_Lumpur",
        )
    )
    monkeypatch.setattr(booking, "booking_dispatcher", SharedCalendarDispatcher(service))

    with TestClient(app) as client:
        resp = client.post("/booking", json=BOOKING_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["dispatched"] is False
    assert body["dry_run"] is True
    assert body["payload"]["calendar_mode"] == "shared"
    assert "Google Calendar credentials file not found" in body["payload"]["calendar_error"]


def test_booking_creates_shared_calendar_event_when_configured(monkeypatch):
    inserted_events = []

    def fake_event_inserter(calendar_id, event):
        inserted_events.append((calendar_id, event))
        return {"id": "shared-event-123", "htmlLink": "https://calendar.google.test/event/123"}

    service = GoogleCalendarService(
        settings=service_account_settings(),
        event_inserter=fake_event_inserter,
    )
    monkeypatch.setattr(booking, "booking_dispatcher", SharedCalendarDispatcher(service))

    with TestClient(app) as client:
        resp = client.post("/booking", json=BOOKING_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "booked"
    assert body["dispatched"] is True
    assert body["dry_run"] is False
    assert body["payload"]["calendar_mode"] == "shared"
    assert body["payload"]["calendar_event_id"] == "shared-event-123"
    assert body["payload"]["calendar_html_link"] == "https://calendar.google.test/event/123"
    assert inserted_events[0][0] == "primary"
    assert inserted_events[0][1]["summary"].startswith("AssetIQ Certified Inspection")

    with SessionLocal() as session:
        row = session.get(orm.Booking, body["booking_id"])
        assert row is not None
        assert row.status == "booked"
        assert row.calendar_event_id == "shared-event-123"
