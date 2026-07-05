from fastapi.testclient import TestClient

from app.main import app
from app.routers import booking as booking_router
from app.services import calendar_agent, telegram_bot


def _payload():
    return {
        "profile_id": 1,
        "name": "Chan",
        "workshop": "Hap Seng Star KL",
        "car_model": "C-Class",
        "purpose": "Certified inspection",
        "date": "2026-07-10",
        "time": "10:00",
    }


def test_availability_lists_free_slots(monkeypatch):
    monkeypatch.setattr(
        booking_router.google_calendar_service,
        "free_slots_for_date",
        lambda date: ["09:00", "10:00"],
    )
    with TestClient(app) as client:
        resp = client.get("/booking/availability", params={"date": "2026-07-10"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == "2026-07-10"
    assert body["slots"] == ["09:00", "10:00"]


def test_post_booking_dispatches_when_telegram_configured(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot, "send_message", lambda text: {"result": {"message_id": 55}}
    )
    with TestClient(app) as client:
        resp = client.post("/booking", json=_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["dispatched"] is True
    assert body["dry_run"] is False


def test_post_booking_dry_run_fallback_when_unconfigured(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: False)
    with TestClient(app) as client:
        resp = client.post("/booking", json=_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["dry_run"] is True


def test_diagnostics_reports_unconfigured_state(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: False)
    with TestClient(app) as client:
        resp = client.get("/booking/diagnostics")
    assert resp.status_code == 200
    body = resp.json()
    # Hermetic test env: everything unconfigured, probe reports the failure.
    assert body["telegram_configured"] is False
    assert body["telegram_webhook_configured"] is False
    assert body["calendar_write_configured"] is False
    assert body["calendar_read_configured"] is False
    assert body["freebusy_probe"].startswith("error")
    assert set(body) >= {
        "telegram_configured",
        "telegram_webhook_configured",
        "gemini_configured",
        "calendar_write_configured",
        "calendar_read_configured",
        "calendar_id",
        "service_account_email",
        "freebusy_probe",
    }

def test_diagnostics_reports_telegram_webhook(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot,
        "get_webhook_info",
        lambda: {"ok": True, "result": {"url": "https://example.test/telegram"}},
    )
    with TestClient(app) as client:
        resp = client.get("/booking/diagnostics")
    assert resp.status_code == 200
    assert resp.json()["telegram_webhook_configured"] is True


def test_check_reply_not_found():
    with TestClient(app) as client:
        resp = client.post("/booking/999999/check-reply")
    assert resp.status_code == 404


def test_check_reply_confirms_and_books(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot, "send_message", lambda text: {"result": {"message_id": 55}}
    )
    with TestClient(app) as client:
        created = client.post("/booking", json=_payload()).json()
        booking_id = created["booking_id"]

        monkeypatch.setattr(
            telegram_bot, "fetch_latest_reply", lambda **kwargs: {"text": "confirm"}
        )
        monkeypatch.setattr(calendar_agent, "classify_reply", lambda text, b: "confirmed")
        monkeypatch.setattr(calendar_agent, "create_calendar_event", lambda b: "evt-1")

        resp = client.post(f"/booking/{booking_id}/check-reply")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "booked"
    assert body["booked"] is True
    assert body["classification"] == "confirmed"

