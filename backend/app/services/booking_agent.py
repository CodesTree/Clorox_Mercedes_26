"""Booking orchestrator: the Telegram-gated state machine.

dispatch_proposal  — send the proposal to Telegram, mark the booking `sent`.
process_reply      — pull the latest reply and advance the booking:
                       confirmed   -> create calendar event -> `booked`
                       unavailable -> find next free slot -> re-propose (`sent`)
                                       (capped at MAX_ROUNDS -> `failed`)
                       unclear/none -> stay `sent` (waiting)
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import orm
from app.schemas import BookingReplyOut
from app.services import calendar_agent, telegram_bot

logger = logging.getLogger(__name__)

MAX_ROUNDS = 3

# Statuses that need no further reply processing.
_TERMINAL_STATUSES = {"booked", "failed", "dry_run"}


def _extract_message_id(response: object) -> str | None:
    if isinstance(response, dict):
        result = response.get("result")
        if isinstance(result, dict) and result.get("message_id") is not None:
            return str(result.get("message_id"))
    return None


def _send_proposal(booking: orm.Booking) -> str | None:
    """Send/re-send the proposal. Returns the message id.

    Raises on send failure so callers can decide how to degrade.
    """
    message = telegram_bot.format_booking_message(booking)
    response = telegram_bot.send_message(message)
    return _extract_message_id(response)


def dispatch_proposal(session: Session, booking: orm.Booking) -> orm.Booking:
    """Send the first proposal. Falls back to dry-run if Telegram is unavailable."""
    if not telegram_bot.is_configured():
        booking.status = "dry_run"
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return booking

    try:
        message_id = _send_proposal(booking)
    except Exception:
        logger.exception("Telegram send failed; marking booking dry_run")
        booking.status = "dry_run"
        booking.telegram_message_id = None
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return booking

    booking.status = "sent"
    booking.telegram_message_id = message_id
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


def process_reply(session: Session, booking: orm.Booking) -> BookingReplyOut:
    if booking.status in _TERMINAL_STATUSES:
        return _reply_out(
            booking,
            booked=booking.status == "booked",
            classification="none",
            message=f"Booking already {booking.status}.",
        )

    if booking.status == "confirmed":
        return _confirm_and_book(session, booking)

    last_update_id = booking.telegram_update_id
    allow_unthreaded = _allow_unthreaded_reply(session)
    offset = (
        (last_update_id + 1)
        if allow_unthreaded and last_update_id is not None
        else None
    )
    reply = telegram_bot.fetch_latest_reply(
        since_dt=booking.updated_at,
        offset=offset,
        reply_to_message_id=booking.telegram_message_id,
        booking_reference=telegram_bot.booking_reference(booking),
        allow_unthreaded=allow_unthreaded,
    )
    if not reply:
        return _reply_out(
            booking,
            booked=False,
            classification="none",
            message="No reply yet. Awaiting workshop confirmation.",
        )

    _remember_update_id(session, booking, reply)
    text = str(reply.get("text", ""))
    intent = calendar_agent.classify_reply(text, booking)

    if intent == "confirmed":
        return _confirm_and_book(session, booking)
    if intent == "unavailable":
        return _reschedule(session, booking)

    return _reply_out(
        booking,
        booked=False,
        classification="unclear",
        message="Reply unclear; still awaiting a clear confirmation.",
    )


def _allow_unthreaded_reply(session: Session) -> bool:
    active_sent = session.query(orm.Booking).filter(orm.Booking.status == "sent").count()
    return active_sent <= 1


def _remember_update_id(session: Session, booking: orm.Booking, reply: dict) -> None:
    update_id = reply.get("_update_id")
    if update_id is None:
        return

    try:
        update_id_int = int(update_id)
    except (TypeError, ValueError):
        return

    if booking.telegram_update_id is None or update_id_int > booking.telegram_update_id:
        booking.telegram_update_id = update_id_int
        session.add(booking)
        session.commit()
        session.refresh(booking)


def _confirm_and_book(session: Session, booking: orm.Booking) -> BookingReplyOut:
    booking.status = "confirmed"
    session.add(booking)
    session.commit()

    try:
        event_id = calendar_agent.create_calendar_event(booking)
    except Exception as exc:
        logger.exception("Calendar event creation failed; falling back to dry-run")
        booking.status = "dry_run"
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return _reply_out(
            booking,
            booked=False,
            classification="confirmed",
            message=f"Confirmed, but calendar unavailable ({exc}); saved as dry-run.",
        )

    booking.calendar_event_id = event_id
    booking.status = "booked"
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return _reply_out(
        booking,
        booked=True,
        classification="confirmed",
        message="Confirmed. Calendar event created.",
    )


def _reschedule(session: Session, booking: orm.Booking) -> BookingReplyOut:
    current_round = booking.negotiation_round or 0
    if current_round >= MAX_ROUNDS:
        booking.status = "failed"
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return _reply_out(
            booking,
            booked=False,
            classification="unavailable",
            message=f"No slot confirmed after {MAX_ROUNDS} proposals.",
        )

    next_date, next_time = calendar_agent.find_next_available_slot(
        booking.date, booking.time
    )
    booking.date = next_date
    booking.time = next_time
    booking.negotiation_round = current_round + 1

    if telegram_bot.is_configured():
        try:
            booking.telegram_message_id = _send_proposal(booking)
            booking.status = "sent"
        except Exception:
            logger.exception("Re-proposal send failed; marking dry_run")
            booking.status = "dry_run"
    else:
        booking.status = "dry_run"

    session.add(booking)
    session.commit()
    session.refresh(booking)
    return _reply_out(
        booking,
        booked=False,
        classification="unavailable",
        message=(
            f"Slot unavailable; proposed {next_date} {next_time} "
            f"(round {booking.negotiation_round})."
        ),
    )


def _reply_out(
    booking: orm.Booking,
    *,
    booked: bool,
    classification: str,
    message: str,
) -> BookingReplyOut:
    return BookingReplyOut(
        booking_id=booking.id,
        status=booking.status,
        booked=booked,
        proposed_date=booking.date,
        proposed_time=booking.time,
        round=booking.negotiation_round or 0,
        classification=classification,
        message=message,
    )
