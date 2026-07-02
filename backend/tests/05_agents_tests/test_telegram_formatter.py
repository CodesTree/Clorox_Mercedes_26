from types import SimpleNamespace
from app.services.telegram_bot import format_booking_message


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