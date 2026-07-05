from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Optional

import httpx
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..orm import Booking
from ..config import get_settings
from .dispatcher import BookingDispatcher, BookingRecord, DispatchResult
from .calendar_agent import resolve_booking

logger = logging.getLogger(__name__)

CONFIRMATION_KEYWORDS = {"confirmed", "approved", "yes", "ok", "okay"}

# TODO: persist offset in DB so restarts don't reprocess or miss updates
# FIX: renamed to consistent module-level state variable
_POLL_SINCE_UPDATE_ID: int = 0


def format_booking_message(booking: BookingRecord) -> str:
    return (
        f"Name: {booking.name}\n"
        f"Nearest Mercedes Workshop: {booking.workshop}\n"
        f"Car model: {booking.car_model}\n"
        f"Purpose: {booking.purpose}\n"
        f"Date: {booking.date}\n"
        f"Time: {booking.time}"
    )


def is_confirmation(text: str) -> bool:
    return text.strip().casefold() in CONFIRMATION_KEYWORDS


def poll_for_confirmation(chat_id: str, since_update_id: int) -> Optional[dict]:
    global _POLL_SINCE_UPDATE_ID  # FIX: consistent naming

    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return None

    normalized_chat_id = str(chat_id)
    if normalized_chat_id != str(settings.telegram_chat_id):
        return None

    effective_since_update_id = max(since_update_id, _POLL_SINCE_UPDATE_ID)

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"

    response = httpx.get(
        url,
        params={"offset": effective_since_update_id + 1, "timeout": 2},
        timeout=5.0,
    )
    response.raise_for_status()

    payload = response.json()
    updates = payload.get("result", []) if isinstance(payload, dict) else []

    for update in updates:
        if not isinstance(update, dict):
            continue

        update_id = update.get("update_id")
        if isinstance(update_id, int):
            _POLL_SINCE_UPDATE_ID = max(_POLL_SINCE_UPDATE_ID, update_id)  # FIX

        message = update.get("message")
        if not isinstance(message, dict):
            continue

        message_chat = message.get("chat")
        message_chat_id = None

        if isinstance(message_chat, dict) and message_chat.get("id") is not None:
            message_chat_id = str(message_chat.get("id"))

        if message_chat_id != normalized_chat_id:
            continue

        text = message.get("text")
        if isinstance(text, str) and is_confirmation(text):
            return message

    return None


def schedule_confirmation_poll(
    background_tasks: BackgroundTasks, chat_id: str, since_update_id: int
) -> None:
    """FastAPI background task polling (hackathon-safe; not production-grade)."""

    background_tasks.add_task(poll_for_confirmation, chat_id, since_update_id)


def _process_confirmation(booking_id: int, chat_id: str, since_update_id: int) -> None:
    session = SessionLocal()
    try:
        booking = session.get(Booking, booking_id)
        if booking is None:
            return

        confirmation = poll_for_confirmation(chat_id, since_update_id)
        if not confirmation:
            return

        booking.status = "confirmed"
        session.add(booking)
        session.commit()

        result = resolve_booking(booking)

        booking.status = str(result.get("status", booking.status))
        booking.calendar_event_id = result.get("calendar_event_id")

        session.add(booking)
        session.commit()

    except Exception:
        session.rollback()
        logger.exception("Confirmation processing failed")
    finally:
        session.close()


def send_message(text: str) -> dict:
    settings = get_settings()

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram credentials are not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    response = httpx.post(
        url,
        json={"chat_id": settings.telegram_chat_id, "text": text},
        timeout=10.0,
    )
    response.raise_for_status()

    return response.json()


class TelegramDispatcher(BookingDispatcher):
    def __init__(self, session: Session, background_tasks: BackgroundTasks | None = None):
        self.session = session
        self.background_tasks = background_tasks

    def dispatch(self, booking: BookingRecord) -> DispatchResult:
        settings = get_settings()

        # =========================
        # DRY RUN (no Telegram config)
        # =========================
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            booking.status = "dry_run"
            booking.telegram_message_id = None
            booking.calendar_event_id = None

            self.session.add(booking)
            self.session.commit()

            return SimpleNamespace(
                status="dry_run",
                telegram_message_id=None,
                calendar_event_id=None,
                dry_run=True,
            )

        # =========================
        # SEND TELEGRAM MESSAGE
        # =========================
        try:
            message = format_booking_message(booking)
            response = send_message(message)

        except Exception:
            # FIX: graceful degradation required by spec
            booking.status = "dry_run"
            booking.telegram_message_id = None
            booking.calendar_event_id = None

            self.session.add(booking)
            self.session.commit()

            logger.exception("Telegram send failed; falling back to dry-run")

            return SimpleNamespace(
                status="dry_run",
                telegram_message_id=None,
                calendar_event_id=None,
                dry_run=True,
            )

        message_id = None
        if isinstance(response, dict):
            result = response.get("result")
            if isinstance(result, dict):
                message_id = str(result.get("message_id"))

        # =========================
        # UPDATE DB → SENT
        # =========================
        booking.status = "sent"
        booking.telegram_message_id = message_id

        self.session.add(booking)
        self.session.commit()

        # =========================
        # BACKGROUND CONFIRMATION POLL
        # =========================
        if self.background_tasks is not None:
            self.background_tasks.add_task(
                _process_confirmation,
                booking.id,
                str(settings.telegram_chat_id),
                _POLL_SINCE_UPDATE_ID,
            )

        return SimpleNamespace(
            status="sent",
            telegram_message_id=message_id,
            calendar_event_id=None,
            dry_run=False,
        )