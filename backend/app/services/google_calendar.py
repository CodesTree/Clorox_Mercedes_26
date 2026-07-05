from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app import orm
from app.config import Settings, get_settings


CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


class GoogleCalendarError(RuntimeError):
    pass


@dataclass(frozen=True)
class CalendarEventResult:
    event_id: str
    html_link: str | None = None


EventInserter = Callable[[str, dict[str, Any]], dict[str, Any]]


def _configured_setting(settings: Settings, field_name: str) -> bool:
    value = getattr(settings, field_name, "")
    was_provided = field_name in getattr(settings, "model_fields_set", set())
    return was_provided and isinstance(value, str) and bool(value.strip())


class GoogleCalendarService:
    """Creates events in a shared AssetIQ/Mercedes Google Calendar."""

    def __init__(
        self,
        settings: Settings | None = None,
        event_inserter: EventInserter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._event_inserter = event_inserter

    @property
    def configured(self) -> bool:
        return self.configuration_error() is None

    def configuration_error(self) -> str | None:
        missing = [
            env_name
            for field_name, env_name in [
                ("google_calendar_credentials_json", "GOOGLE_CALENDAR_CREDENTIALS_JSON"),
                ("google_calendar_id", "GOOGLE_CALENDAR_ID"),
            ]
            if not _configured_setting(self.settings, field_name)
        ]
        if missing:
            return f"Shared Google Calendar is not configured. Missing: {', '.join(missing)}."

        credentials_source = self.settings.google_calendar_credentials_json.strip()
        if credentials_source.startswith("{"):
            return None

        credentials_path = Path(credentials_source)
        if not credentials_path.exists():
            return (
                f"Google Calendar credentials file not found: {credentials_path}. "
                "Add the service account JSON file or update GOOGLE_CALENDAR_CREDENTIALS_JSON."
            )
        if not credentials_path.is_file():
            return f"Google Calendar credentials path is not a file: {credentials_path}."

        return None

    def build_booking_event(self, booking: orm.Booking) -> dict[str, Any]:
        timezone_name = self.settings.google_calendar_timezone
        try:
            tzinfo = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            tzinfo = dt_timezone(timedelta(hours=8))

        start = datetime.fromisoformat(f"{booking.date}T{booking.time}:00").replace(
            tzinfo=tzinfo
        )
        end = start + timedelta(hours=1)

        return {
            "summary": f"AssetIQ Certified Inspection - {booking.car_model}",
            "description": (
                f"Purpose: {booking.purpose}\n"
                f"Name: {booking.name}\n"
                "Booked through AssetIQ for Mercedes-Benz."
            ),
            "location": booking.workshop,
            "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
            "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "email", "minutes": 60}],
            },
        }

    def create_booking_event(self, booking: orm.Booking) -> CalendarEventResult:
        config_error = self.configuration_error()
        if config_error is not None:
            raise GoogleCalendarError(config_error)

        event = self.build_booking_event(booking)
        if self._event_inserter is not None:
            response = self._event_inserter(self.settings.google_calendar_id, event)
        else:
            response = self.insert_event(self.settings.google_calendar_id, event)

        event_id = response.get("id") if isinstance(response, dict) else None
        if not event_id:
            raise GoogleCalendarError("Calendar API response missing event id")

        html_link = response.get("htmlLink") if isinstance(response, dict) else None
        return CalendarEventResult(event_id=str(event_id), html_link=html_link)

    def insert_event(self, calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """Insert a pre-built event payload into the given calendar.

        Public so callers with their own payload-building logic (e.g. the
        Telegram-confirmation calendar agent) can reuse this credential/SDK
        plumbing instead of duplicating it.
        """
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleCalendarError(
                "Google Calendar dependencies missing. Install backend requirements."
            ) from exc

        credentials_source = self.settings.google_calendar_credentials_json.strip()
        if credentials_source.startswith("{"):
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(credentials_source), scopes=[CALENDAR_SCOPE]
            )
        else:
            credentials_path = Path(credentials_source)
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=[CALENDAR_SCOPE]
            )

        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return service.events().insert(calendarId=calendar_id, body=event).execute()


google_calendar_service = GoogleCalendarService()
