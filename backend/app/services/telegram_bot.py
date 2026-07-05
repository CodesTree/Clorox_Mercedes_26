"""Thin Telegram I/O for the booking agent.

Outbound: send the appointment proposal to the configured chat.
Inbound: pull the latest text reply from that chat (manual, on-demand poll).

All functions degrade gracefully: when Telegram is not configured the caller is
expected to fall back to dry-run behaviour (see booking_agent).
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app import orm
from app.config import get_settings

logger = logging.getLogger(__name__)

_API_ROOT = "https://api.telegram.org/bot{token}/{method}"


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.telegram_bot_token.strip()) and bool(
        str(settings.telegram_chat_id).strip()
    )


def booking_reference(booking: orm.Booking) -> str:
    return f"BKG-{booking.id}"


def format_booking_message(booking: orm.Booking) -> str:
    """Exact outbound payload shape agreed for the demo."""
    reference = (
        f"Booking ref: {booking_reference(booking)}\n"
        if getattr(booking, "id", None)
        else ""
    )
    return (
        f"{reference}"
        f"Name: {booking.name}\n"
        f"Nearest Mercedes Workshop: {booking.workshop}\n"
        f"Car model: {booking.car_model}\n"
        f"Purpose: {booking.purpose}\n"
        f"Date: {booking.date}\n"
        f"Time: {booking.time}\n"
        "\nReply CONFIRM to book, or tell us if the slot is unavailable."
    )


def send_message(text: str) -> dict:
    settings = get_settings()
    if not is_configured():
        raise RuntimeError("Telegram credentials are not configured")

    url = _API_ROOT.format(token=settings.telegram_bot_token, method="sendMessage")
    response = httpx.post(
        url,
        json={"chat_id": settings.telegram_chat_id, "text": text},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def get_webhook_info() -> dict | None:
    settings = get_settings()
    if not is_configured():
        return None

    url = _API_ROOT.format(token=settings.telegram_bot_token, method="getWebhookInfo")
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception:
        logger.exception("Telegram getWebhookInfo failed")
        return None


def fetch_latest_reply(
    since_dt: datetime | None = None,
    *,
    offset: int | None = None,
    reply_to_message_id: str | None = None,
    booking_reference: str | None = None,
    allow_unthreaded: bool = True,
) -> dict | None:
    """Return the most recent text message from the configured chat.

    Only messages at/after `since_dt` are considered, so each negotiation round
    ignores replies to earlier proposals. `offset` is forwarded to Telegram so
    callers can process each update once. When a message id or booking reference
    is supplied, replies are matched to that booking; plain chat replies are only
    accepted when `allow_unthreaded` is true.
    """
    settings = get_settings()
    if not is_configured():
        return None

    url = _API_ROOT.format(token=settings.telegram_bot_token, method="getUpdates")
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset

    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("Telegram getUpdates failed")
        return None

    logger.debug("Telegram getUpdates payload: %s", payload)
    updates = payload.get("result", []) if isinstance(payload, dict) else []
    chat_id = str(settings.telegram_chat_id)
    # Telegram message dates are whole seconds; DB timestamps may include
    # microseconds, so compare at second precision to avoid dropping a valid
    # immediate reply from the same second as booking.updated_at.
    since_ts = int(since_dt.timestamp()) if since_dt is not None else None

    latest: dict | None = None
    latest_ts = -1.0
    for update in updates:
        logger.debug("Telegram update: %s", update)
        if not isinstance(update, dict):
            logger.debug("Skipping Telegram update: not an object")
            continue

        update_id = update.get("update_id")
        message = update.get("message")
        if not isinstance(message, dict):
            logger.debug("Skipping Telegram update %s: no message", update_id)
            continue

        logger.debug("Telegram message: %s", message)
        chat = message.get("chat")
        if not isinstance(chat, dict) or str(chat.get("id")) != chat_id:
            logger.debug("Skipping Telegram update %s: chat mismatch", update_id)
            continue

        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            logger.debug("Skipping Telegram update %s: empty text", update_id)
            continue

        msg_ts = int(float(message.get("date", 0) or 0))
        if since_ts is not None and msg_ts < since_ts:
            logger.debug("Skipping Telegram update %s: before since_dt", update_id)
            continue

        if not _matches_booking_reply(
            message,
            text=text,
            reply_to_message_id=reply_to_message_id,
            booking_reference=booking_reference,
            allow_unthreaded=allow_unthreaded,
        ):
            logger.debug("Skipping Telegram update %s: booking mismatch", update_id)
            continue

        if msg_ts >= latest_ts:
            latest_ts = msg_ts
            latest = dict(message)
            latest["_update_id"] = update_id

    return latest


def _matches_booking_reply(
    message: dict,
    *,
    text: str,
    reply_to_message_id: str | None,
    booking_reference: str | None,
    allow_unthreaded: bool,
) -> bool:
    if booking_reference and booking_reference.lower() in text.lower():
        return True

    if reply_to_message_id:
        reply_to = message.get("reply_to_message")
        if isinstance(reply_to, dict) and str(reply_to.get("message_id")) == str(
            reply_to_message_id
        ):
            return True

    return allow_unthreaded
