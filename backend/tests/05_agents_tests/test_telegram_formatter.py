from types import SimpleNamespace

from app.services import telegram_bot
from app.services.telegram_bot import (
    format_booking_message,
    is_confirmation,
    poll_for_confirmation,
    schedule_confirmation_poll,
)


def test_format_booking_message_has_all_six_fields():
    fake_booking = SimpleNamespace(
        name="John Doe",
        workshop="Mercedes Klang",
        car_model="C-Class",
        purpose="Service",
        date="2026-07-03",
        time="10:30",
    )

    msg = format_booking_message(fake_booking)

    expected_labels = [
        "Name",
        "Nearest Mercedes Workshop",
        "Car model",
        "Purpose",
        "Date",
        "Time",
    ]

    for label in expected_labels:
        assert label in msg


def test_format_booking_message_structure_snapshot():
    fake_booking = SimpleNamespace(
        name="Alice Tan",
        workshop="Mercedes Petaling Jaya",
        car_model="E-Class",
        purpose="Repair",
        date="2026-08-01",
        time="14:00",
    )

    msg = format_booking_message(fake_booking)

    # basic structural checks (more strict than just label presence)
    lines = msg.split("\n")

    assert len(lines) == 6
    assert lines[0].startswith("Name:")
    assert lines[1].startswith("Nearest Mercedes Workshop:")
    assert lines[2].startswith("Car model:")
    assert lines[3].startswith("Purpose:")
    assert lines[4].startswith("Date:")
    assert lines[5].startswith("Time:")


def test_is_confirmation_exact_match_only():
    assert is_confirmation("confirmed")
    assert is_confirmation(" APPROVED ")
    assert is_confirmation("Yes")
    assert not is_confirmation("not confirmed")
    assert not is_confirmation("confirmed please")
    assert not is_confirmation("okay then")


def test_poll_for_confirmation_filters_chat_and_tracks_offset(monkeypatch):
    telegram_bot.POLL_SINCE_UPDATE_ID = 0

    settings = SimpleNamespace(
        telegram_bot_token="token-123",
        telegram_chat_id="987654321",
    )
    monkeypatch.setattr(telegram_bot, "get_settings", lambda: settings)

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ok": True,
                "result": [
                    {
                        "update_id": 41,
                        "message": {
                            "chat": {"id": "987654321"},
                            "text": "not confirmed",
                        },
                    },
                    {
                        "update_id": 42,
                        "message": {
                            "chat": {"id": "111"},
                            "text": "confirmed",
                        },
                    },
                    {
                        "update_id": 43,
                        "message": {
                            "chat": {"id": "987654321"},
                            "text": "  confirmed  ",
                        },
                    },
                ],
            }

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(telegram_bot.httpx, "get", fake_get)

    message = poll_for_confirmation("987654321", 7)

    assert captured["url"].endswith("/getUpdates")
    assert captured["params"] == {"offset": 8, "timeout": 2}
    assert captured["timeout"] == 5.0
    assert message["text"] == "  confirmed  "
    assert telegram_bot.POLL_SINCE_UPDATE_ID == 43


def test_schedule_confirmation_poll_uses_background_tasks():
    captured = {}

    class FakeBackgroundTasks:
        def add_task(self, func, *args, **kwargs):
            captured["func"] = func
            captured["args"] = args
            captured["kwargs"] = kwargs

    schedule_confirmation_poll(FakeBackgroundTasks(), "987654321", 12)

    assert captured["func"] is poll_for_confirmation
    assert captured["args"] == ("987654321", 12)
    assert captured["kwargs"] == {}