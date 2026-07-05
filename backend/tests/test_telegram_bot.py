from types import SimpleNamespace

from app.services.telegram_bot import format_booking_message, is_confirmation


def test_format_booking_message_has_all_six_fields():
    booking = SimpleNamespace(
        name="John Doe",
        workshop="Mercedes Klang",
        car_model="C-Class",
        purpose="Service",
        date="2026-07-03",
        time="10:30",
    )

    assert format_booking_message(booking).splitlines() == [
        "Name: John Doe",
        "Nearest Mercedes Workshop: Mercedes Klang",
        "Car model: C-Class",
        "Purpose: Service",
        "Date: 2026-07-03",
        "Time: 10:30",
    ]


def test_confirmation_detection_accepts_and_rejects_exact_matches():
    accepted = ["confirmed", " APPROVED ", "Yes", "ok", "okay"]
    rejected = ["not confirmed", "confirmed please", "okay then", "yes sir"]

    for text in accepted:
        assert is_confirmation(text)

    for text in rejected:
        assert not is_confirmation(text)