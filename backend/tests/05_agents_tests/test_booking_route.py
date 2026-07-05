from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.db import engine
from app.main import app
from app import orm
from app.services import telegram_bot
from app.services.vehicle import ensure_default_profile


def _booking_payload(profile_id: int) -> dict:
    return {
        "profile_id": profile_id,
        "name": "Aisha Rahman",
        "workshop": "Mercedes PJ",
        "car_model": "C-Class",
        "purpose": "Inspection",
        "date": "2026-07-10",
        "time": "09:30",
    }


def _create_profile() -> int:
    orm.Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        # Seed the app's own default profile first so it keeps id=1; other
        # test modules (e.g. test_phase03_api.py) assume id=1 is the SL CLASS
        # demo profile seeded on first access.
        ensure_default_profile(session)

        profile = orm.VehicleProfile(
            name="Aisha Rahman",
            model="C-Class",
            year=2022,
            mileage=12000,
            transmission="Automatic",
            fuel_type="Petrol",
            engine_size=2.0,
            workshop="Mercedes PJ",
            glb_asset=None,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile.id


def test_booking_route_updates_row_after_confirmation(monkeypatch):
    profile_id = _create_profile()

    settings = SimpleNamespace(
        telegram_bot_token="token-123",
        telegram_chat_id="987654321",
        gemini_api_key="gemini-key",
        google_calendar_credentials_json="service-account.json",
        google_calendar_id="calendar-id",
    )

    monkeypatch.setattr(telegram_bot, "get_settings", lambda: settings)
    monkeypatch.setattr(
        telegram_bot,
        "send_message",
        lambda text: {"ok": True, "result": {"message_id": 77}},
    )
    monkeypatch.setattr(
        telegram_bot,
        "poll_for_confirmation",
        lambda chat_id, since_update_id: {"text": "confirmed", "chat": {"id": chat_id}},
    )
    monkeypatch.setattr(
        telegram_bot,
        "resolve_booking",
        lambda booking: {"status": "booked", "calendar_event_id": "evt-123", "dry_run": False},
    )

    with TestClient(app) as client:
        response = client.post("/booking", json=_booking_payload(profile_id))

    assert response.status_code == 200
    response_body = response.json()
    assert response_body["booking_id"] > 0
    assert response_body["status"] == "sent"
    assert response_body["dispatched"] is True
    assert response_body["dry_run"] is False

    with SessionLocal() as session:
        booking = session.scalar(
            select(orm.Booking)
            .where(orm.Booking.profile_id == profile_id)
            .order_by(orm.Booking.id.desc())
        )

    assert booking is not None
    assert booking.status == "booked"
    assert booking.telegram_message_id == "77"
    assert booking.calendar_event_id == "evt-123"


def test_booking_route_returns_dry_run_when_telegram_fails(monkeypatch):
    profile_id = _create_profile()

    settings = SimpleNamespace(
        telegram_bot_token="token-123",
        telegram_chat_id="987654321",
        gemini_api_key="",
        google_calendar_credentials_json="",
        google_calendar_id="",
    )

    monkeypatch.setattr(telegram_bot, "get_settings", lambda: settings)
    monkeypatch.setattr(telegram_bot, "send_message", lambda text: (_ for _ in ()).throw(RuntimeError("network down")))

    with TestClient(app) as client:
        response = client.post("/booking", json=_booking_payload(profile_id))

    assert response.status_code == 200
    response_body = response.json()
    assert response_body["booking_id"] > 0
    assert response_body["status"] == "dry_run"
    assert response_body["dispatched"] is False
    assert response_body["dry_run"] is True

    with SessionLocal() as session:
        booking = session.scalar(
            select(orm.Booking)
            .where(orm.Booking.profile_id == profile_id)
            .order_by(orm.Booking.id.desc())
        )

    assert booking is not None
    assert booking.status == "dry_run"
    assert booking.telegram_message_id is None
    assert booking.calendar_event_id is None

def test_booking_route_all_env_vars_unset_returns_dry_run(monkeypatch):
    profile_id = _create_profile()

    # FIX: fully simulate "no configuration environment"
    settings = SimpleNamespace(
        telegram_bot_token="",
        telegram_chat_id="",
        gemini_api_key="",
        google_calendar_credentials_json="",
        google_calendar_id="",
    )

    monkeypatch.setattr(telegram_bot, "get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.post("/booking", json=_booking_payload(profile_id))

    assert response.status_code == 200

    body = response.json()

    # FIX: contract-level assertion (required by spec)
    assert body["status"] == "dry_run"
    assert body["dry_run"] is True