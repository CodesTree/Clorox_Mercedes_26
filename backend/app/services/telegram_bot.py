from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

import httpx
from fastapi import BackgroundTasks

from ..config import get_settings
from .dispatcher import BookingDispatcher, BookingRecord, DispatchResult


CONFIRMATION_KEYWORDS = {"confirmed", "approved", "yes", "ok", "okay"}

# TODO: persist offset in the DB so restarts don't reprocess or miss updates
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
    global POLL_SINCE_UPDATE_ID

    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return None

    normalized_chat_id = str(chat_id)
    if normalized_chat_id != str(settings.telegram_chat_id):
        return None

    effective_since_update_id = max(since_update_id, POLL_SINCE_UPDATE_ID)
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
            POLL_SINCE_UPDATE_ID = max(POLL_SINCE_UPDATE_ID, update_id)

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
    """polling runs as a FastAPI background task; acceptable for hackathon scope, would need a durable worker + persisted offset for production."""

    background_tasks.add_task(poll_for_confirmation, chat_id, since_update_id)


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
    def dispatch(self, booking: BookingRecord) -> DispatchResult:
        settings = get_settings()
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return SimpleNamespace(
                status="dry_run",
                telegram_message_id=None,
                calendar_event_id=None,
                dry_run=True,
            )

        message = format_booking_message(booking)
        response = send_message(message)
        message_id = None
        if isinstance(response, dict):
            result = response.get("result")
            if isinstance(result, dict):
                message_id = str(result.get("message_id")) if result.get("message_id") is not None else None

        return SimpleNamespace(
            status="sent",
            telegram_message_id=message_id,
            calendar_event_id=None,
            dry_run=False,
        )