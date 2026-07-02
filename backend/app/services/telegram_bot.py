from __future__ import annotations

from types import SimpleNamespace

import httpx

from ..config import get_settings
from .dispatcher import BookingDispatcher, BookingRecord, DispatchResult


def format_booking_message(booking: BookingRecord) -> str:
    return (
        f"Name: {booking.name}\n"
        f"Nearest Mercedes Workshop: {booking.workshop}\n"
        f"Car model: {booking.car_model}\n"
        f"Purpose: {booking.purpose}\n"
        f"Date: {booking.date}\n"
        f"Time: {booking.time}"
    )


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