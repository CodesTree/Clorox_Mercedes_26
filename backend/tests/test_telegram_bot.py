from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import orm
from app.services import telegram_bot


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _booking(**overrides):
    data = dict(
        name="Chan",
        workshop="Hap Seng Star KL",
        car_model="C-Class",
        purpose="Certified inspection",
        date="2026-07-10",
        time="10:00",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_format_booking_message_exact_shape():
    message = telegram_bot.format_booking_message(_booking())
    assert message.startswith(
        "Name: Chan\n"
        "Nearest Mercedes Workshop: Hap Seng Star KL\n"
        "Car model: C-Class\n"
        "Purpose: Certified inspection\n"
        "Date: 2026-07-10\n"
        "Time: 10:00\n"
    )
    assert "CONFIRM" in message


def test_is_configured(monkeypatch):
    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="t", telegram_chat_id="123"),
    )
    assert telegram_bot.is_configured() is True

    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="", telegram_chat_id=""),
    )
    assert telegram_bot.is_configured() is False


def test_send_message_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: False)
    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="", telegram_chat_id=""),
    )
    with pytest.raises(RuntimeError):
        telegram_bot.send_message("hi")


def test_fetch_latest_reply_filters_by_chat_and_time(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="t", telegram_chat_id="123"),
    )

    since = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)
    after = since.timestamp() + 60
    before = since.timestamp() - 60

    payload = {
        "result": [
            {"update_id": 1, "message": {"chat": {"id": 123}, "text": "old", "date": before}},
            {"update_id": 2, "message": {"chat": {"id": 123}, "text": "CONFIRM", "date": after}},
            {"update_id": 3, "message": {"chat": {"id": 999}, "text": "other chat", "date": after + 10}},
        ]
    }
    monkeypatch.setattr(telegram_bot.httpx, "get", lambda *a, **k: FakeResp(payload))

    reply = telegram_bot.fetch_latest_reply(since_dt=since)
    assert reply is not None
    assert reply["text"] == "CONFIRM"

def test_fetch_latest_reply_allows_same_second_reply_and_uses_offset(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="t", telegram_chat_id="123"),
    )

    seen_params = {}

    def fake_get(*args, **kwargs):
        seen_params.update(kwargs.get("params", {}))
        return FakeResp(
            {
                "result": [
                    {
                        "update_id": 42,
                        "message": {
                            "chat": {"id": 123},
                            "text": "CONFIRM",
                            "date": 1783245600,
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr(telegram_bot.httpx, "get", fake_get)

    since = datetime.fromtimestamp(1783245600.900, tz=timezone.utc)
    reply = telegram_bot.fetch_latest_reply(since_dt=since, offset=41)

    assert seen_params["offset"] == 41
    assert reply is not None
    assert reply["text"] == "CONFIRM"
    assert reply["_update_id"] == 42


def test_fetch_latest_reply_requires_thread_or_reference_when_unthreaded_disabled(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="t", telegram_chat_id="123"),
    )

    payload = {
        "result": [
            {
                "update_id": 5,
                "message": {
                    "chat": {"id": 123},
                    "text": "CONFIRM",
                    "date": 1783245600,
                },
            },
            {
                "update_id": 6,
                "message": {
                    "chat": {"id": 123},
                    "text": "CONFIRM",
                    "date": 1783245601,
                    "reply_to_message": {"message_id": 77},
                },
            },
        ]
    }
    monkeypatch.setattr(telegram_bot.httpx, "get", lambda *a, **k: FakeResp(payload))

    reply = telegram_bot.fetch_latest_reply(
        reply_to_message_id="77",
        booking_reference="BKG-9",
        allow_unthreaded=False,
    )

    assert reply is not None
    assert reply["_update_id"] == 6


def test_get_webhook_info_returns_payload_when_configured(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(
        telegram_bot,
        "get_settings",
        lambda: SimpleNamespace(telegram_bot_token="t", telegram_chat_id="123"),
    )
    monkeypatch.setattr(
        telegram_bot.httpx,
        "get",
        lambda *a, **k: FakeResp(
            {"ok": True, "result": {"url": "https://example.test/tg"}}
        ),
    )

    assert telegram_bot.get_webhook_info() == {
        "ok": True,
        "result": {"url": "https://example.test/tg"},
    }


def test_fetch_latest_reply_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: False)
    assert telegram_bot.fetch_latest_reply() is None

