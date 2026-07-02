from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .dispatcher import BookingRecord


def build_event_payload(booking: BookingRecord) -> dict:
    kuala_lumpur_tz = timezone(timedelta(hours=8), name="Asia/Kuala_Lumpur")
    start = datetime.strptime(
        f"{booking.date} {booking.time}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=kuala_lumpur_tz)
    end = start + timedelta(hours=1)

    return {
        "summary": f"Mercedes Inspection — {booking.car_model}",
        "description": f"Purpose: {booking.purpose}\nName: {booking.name}",
        "location": booking.workshop,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "Asia/Kuala_Lumpur",
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "Asia/Kuala_Lumpur",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {
                    "method": "email",
                    "minutes": 60,
                }
            ],
        },
    }