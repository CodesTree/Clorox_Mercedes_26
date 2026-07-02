from types import SimpleNamespace

from app.services.calendar_agent import build_event_payload
from datetime import datetime
from dateutil.parser import parse


def test_build_event_payload_creates_calendar_body():
    booking = SimpleNamespace(
        name="Aisha Rahman",
        workshop="Mercedes PJ",
        car_model="C-Class",
        purpose="Inspection",
        date="2026-07-10",
        time="09:30",
    )

    payload = build_event_payload(booking)

    assert payload["summary"] == "Mercedes Inspection — C-Class"
    assert payload["description"] == "Purpose: Inspection\nName: Aisha Rahman"
    assert payload["location"] == "Mercedes PJ"
    assert payload["start"]["dateTime"] == "2026-07-10T09:30:00+08:00"
    assert payload["start"]["timeZone"] == "Asia/Kuala_Lumpur"
    assert payload["end"]["dateTime"] == "2026-07-10T10:30:00+08:00"
    assert payload["end"]["timeZone"] == "Asia/Kuala_Lumpur"

    start = parse(payload["start"]["dateTime"])
    end = parse(payload["end"]["dateTime"])

    assert (end - start).total_seconds() == 3600
    
    assert payload["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "email", "minutes": 60}],
    }

    