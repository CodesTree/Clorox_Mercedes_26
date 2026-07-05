import pytest

from app import orm
from app.db import SessionLocal, init_db
from app.services import booking_agent, calendar_agent, telegram_bot


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _make_booking(session, **overrides):
    data = dict(
        profile_id=1,
        name="Chan",
        workshop="Hap Seng Star KL",
        car_model="C-Class",
        purpose="Certified inspection",
        date="2026-07-10",
        time="10:00",
        status="pending",
        negotiation_round=0,
    )
    data.update(overrides)
    booking = orm.Booking(**data)
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


# --- dispatch_proposal -------------------------------------------------------

def test_dispatch_proposal_sends_and_marks_sent(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot, "send_message", lambda text: {"result": {"message_id": 77}}
    )
    with SessionLocal() as session:
        booking = _make_booking(session)
        out = booking_agent.dispatch_proposal(session, booking)
        assert out.status == "sent"
        assert out.telegram_message_id == "77"


def test_dispatch_proposal_dry_run_when_unconfigured(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: False)
    with SessionLocal() as session:
        booking = _make_booking(session)
        out = booking_agent.dispatch_proposal(session, booking)
        assert out.status == "dry_run"


def test_dispatch_proposal_dry_run_on_send_failure(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)

    def boom(text):
        raise RuntimeError("network down")

    monkeypatch.setattr(telegram_bot, "send_message", boom)
    with SessionLocal() as session:
        booking = _make_booking(session)
        out = booking_agent.dispatch_proposal(session, booking)
        assert out.status == "dry_run"
        assert out.telegram_message_id is None


# --- process_reply -----------------------------------------------------------

def test_process_reply_no_reply_stays_sent(monkeypatch):
    monkeypatch.setattr(telegram_bot, "fetch_latest_reply", lambda **kwargs: None)
    with SessionLocal() as session:
        booking = _make_booking(session, status="sent")
        result = booking_agent.process_reply(session, booking)
        assert result.status == "sent"
        assert result.booked is False
        assert result.classification == "none"


def test_process_reply_confirmed_books(monkeypatch):
    monkeypatch.setattr(
        telegram_bot, "fetch_latest_reply", lambda **kwargs: {"text": "confirm"}
    )
    monkeypatch.setattr(calendar_agent, "classify_reply", lambda text, b: "confirmed")
    monkeypatch.setattr(calendar_agent, "create_calendar_event", lambda b: "evt-9")
    with SessionLocal() as session:
        booking = _make_booking(session, status="sent")
        result = booking_agent.process_reply(session, booking)
        assert result.status == "booked"
        assert result.booked is True
        assert booking.calendar_event_id == "evt-9"


def test_process_reply_confirmed_calendar_failure_falls_back(monkeypatch):
    monkeypatch.setattr(
        telegram_bot, "fetch_latest_reply", lambda **kwargs: {"text": "confirm"}
    )
    monkeypatch.setattr(calendar_agent, "classify_reply", lambda text, b: "confirmed")

    def boom(b):
        raise RuntimeError("calendar down")

    monkeypatch.setattr(calendar_agent, "create_calendar_event", boom)
    with SessionLocal() as session:
        booking = _make_booking(session, status="sent")
        result = booking_agent.process_reply(session, booking)
        assert result.status == "dry_run"
        assert result.booked is False


def test_process_reply_unavailable_reschedules_and_resends(monkeypatch):
    monkeypatch.setattr(
        telegram_bot, "fetch_latest_reply", lambda **kwargs: {"text": "taken"}
    )
    monkeypatch.setattr(calendar_agent, "classify_reply", lambda text, b: "unavailable")
    monkeypatch.setattr(
        calendar_agent,
        "find_next_available_slot",
        lambda date, time: ("2026-07-11", "09:00"),
    )
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot, "send_message", lambda text: {"result": {"message_id": 88}}
    )
    with SessionLocal() as session:
        booking = _make_booking(session, status="sent")
        result = booking_agent.process_reply(session, booking)
        assert result.status == "sent"
        assert result.round == 1
        assert result.proposed_date == "2026-07-11"
        assert result.proposed_time == "09:00"
        assert booking.telegram_message_id == "88"


def test_process_reply_unavailable_round_cap_fails(monkeypatch):
    monkeypatch.setattr(
        telegram_bot, "fetch_latest_reply", lambda **kwargs: {"text": "taken"}
    )
    monkeypatch.setattr(calendar_agent, "classify_reply", lambda text, b: "unavailable")
    with SessionLocal() as session:
        booking = _make_booking(session, status="sent", negotiation_round=3)
        result = booking_agent.process_reply(session, booking)
        assert result.status == "failed"
        assert result.booked is False

def test_process_reply_uses_update_offset_and_stores_processed_update(monkeypatch):
    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return {"text": "confirm", "_update_id": 12}

    monkeypatch.setattr(telegram_bot, "fetch_latest_reply", fake_fetch)
    monkeypatch.setattr(calendar_agent, "classify_reply", lambda text, b: "confirmed")
    monkeypatch.setattr(calendar_agent, "create_calendar_event", lambda b: "evt-12")
    with SessionLocal() as session:
        session.query(orm.Booking).filter(orm.Booking.status == "sent").update(
            {"status": "booked"}
        )
        session.commit()
        booking = _make_booking(
            session,
            status="sent",
            telegram_message_id="77",
            telegram_update_id=10,
        )
        result = booking_agent.process_reply(session, booking)
        session.refresh(booking)

        assert result.status == "booked"
        assert calls[0]["offset"] == 11
        assert calls[0]["reply_to_message_id"] == "77"
        assert calls[0]["booking_reference"] == "BKG-" + str(booking.id)
        assert booking.telegram_update_id == 12


def test_process_reply_rejects_unthreaded_reply_when_multiple_bookings_are_sent(monkeypatch):
    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(telegram_bot, "fetch_latest_reply", fake_fetch)
    with SessionLocal() as session:
        first = _make_booking(session, status="sent", telegram_message_id="77")
        _make_booking(session, status="sent", telegram_message_id="88")

        result = booking_agent.process_reply(session, first)

        assert result.status == "sent"
        assert calls[0]["allow_unthreaded"] is False
def test_process_reply_does_not_use_per_booking_offset_with_multiple_sent_bookings(monkeypatch):
    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(telegram_bot, "fetch_latest_reply", fake_fetch)
    with SessionLocal() as session:
        first = _make_booking(
            session,
            status="sent",
            telegram_message_id="77",
            telegram_update_id=10,
        )
        _make_booking(session, status="sent", telegram_message_id="88")

        booking_agent.process_reply(session, first)

        assert calls[0]["offset"] is None

def test_process_reply_unclear_stays_sent(monkeypatch):
    monkeypatch.setattr(
        telegram_bot, "fetch_latest_reply", lambda **kwargs: {"text": "hmm"}
    )
    monkeypatch.setattr(calendar_agent, "classify_reply", lambda text, b: "unclear")
    with SessionLocal() as session:
        booking = _make_booking(session, status="sent")
        result = booking_agent.process_reply(session, booking)
        assert result.status == "sent"
        assert result.classification == "unclear"


