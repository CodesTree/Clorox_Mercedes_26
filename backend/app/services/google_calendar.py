from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app import orm
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Full calendar scope covers both event writes and freebusy reads with one
# service-account credential (the SA's access to a given calendar is governed by
# that calendar's sharing ACL, not by the scope).
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Working-hours window for bookable slots (local calendar time).
WORKING_START_HOUR = 9
WORKING_END_HOUR = 18  # last slot starts at 17:00, ends 18:00
SLOT_HOURS = 1


class GoogleCalendarError(RuntimeError):
    pass


@dataclass(frozen=True)
class CalendarEventResult:
    event_id: str
    html_link: str | None = None


EventInserter = Callable[[str, dict[str, Any]], dict[str, Any]]
FreeBusyQuery = Callable[[dict[str, Any]], dict[str, Any]]


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
        freebusy_query: FreeBusyQuery | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._event_inserter = event_inserter
        self._freebusy_query = freebusy_query

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

    def _resolve_tzinfo(self):
        try:
            return ZoneInfo(self.settings.google_calendar_timezone)
        except ZoneInfoNotFoundError:
            return dt_timezone(timedelta(hours=8))

    def build_booking_event(self, booking: orm.Booking) -> dict[str, Any]:
        timezone_name = self.settings.google_calendar_timezone
        tzinfo = self._resolve_tzinfo()

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

    def _load_credentials(self):
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise GoogleCalendarError(
                "Google Calendar dependencies missing. Install backend requirements."
            ) from exc

        source = self.settings.google_calendar_credentials_json.strip()
        if not source:
            raise GoogleCalendarError("Service account credentials not configured")

        if source.startswith("{"):
            return service_account.Credentials.from_service_account_info(
                json.loads(source), scopes=CALENDAR_SCOPES
            )
        return service_account.Credentials.from_service_account_file(
            Path(source), scopes=CALENDAR_SCOPES
        )

    def _build_service(self):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleCalendarError(
                "Google Calendar dependencies missing. Install backend requirements."
            ) from exc
        return build(
            "calendar", "v3", credentials=self._load_credentials(), cache_discovery=False
        )

    def _insert_event(self, calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
        service = self._build_service()
        return service.events().insert(calendarId=calendar_id, body=event).execute()

    def service_account_email(self) -> str | None:
        """The SA client_email (an identifier, not a secret) to share the calendar with."""
        source = self.settings.google_calendar_credentials_json.strip()
        if not source:
            return None
        try:
            if source.startswith("{"):
                data = json.loads(source)
            else:
                path = Path(source)
                if not path.is_file():
                    return None
                data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        email = data.get("client_email") if isinstance(data, dict) else None
        return str(email) if email else None

    # --- read-only availability (FreeBusy) -----------------------------------
    #
    # Reads use the SAME service account as event writes. An API key can only read
    # public calendars; a private/shared calendar needs the SA (with the calendar
    # shared to the SA's client_email). Failures raise GoogleCalendarError so
    # callers can fall back to a deterministic "assume free" result.

    @property
    def read_configured(self) -> bool:
        return self.configured

    def query_freebusy(
        self, time_min: datetime, time_max: datetime
    ) -> list[tuple[datetime, datetime]]:
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": self.settings.google_calendar_id}],
        }

        if self._freebusy_query is not None:
            response = self._freebusy_query(body)
        else:
            if not _configured_setting(self.settings, "google_calendar_credentials_json"):
                raise GoogleCalendarError("Service account credentials not configured")
            service = self._build_service()
            response = service.freebusy().query(body=body).execute()

        calendars = response.get("calendars", {}) if isinstance(response, dict) else {}
        entry = calendars.get(self.settings.google_calendar_id, {})
        busy: list[tuple[datetime, datetime]] = []
        for slot in entry.get("busy", []) or []:
            try:
                start = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            busy.append((start, end))
        return busy

    def _candidate_slots(self, date_str: str) -> list[datetime]:
        tzinfo = self._resolve_tzinfo()
        day = datetime.fromisoformat(f"{date_str}T00:00:00").replace(tzinfo=tzinfo)
        return [
            day.replace(hour=hour, minute=0)
            for hour in range(WORKING_START_HOUR, WORKING_END_HOUR)
        ]

    def free_slots_for_date(self, date_str: str) -> list[str]:
        """Return free 'HH:MM' slot starts within working hours for the date.

        Falls back to all working-hours slots (assume free) when the calendar
        read is unconfigured or the FreeBusy call fails.
        """
        candidates = self._candidate_slots(date_str)
        if not candidates:
            return []

        try:
            time_min = candidates[0]
            time_max = candidates[-1] + timedelta(hours=SLOT_HOURS)
            busy = self.query_freebusy(time_min, time_max)
        except Exception as exc:  # includes GoogleCalendarError + googleapiclient HttpError
            logger.warning(
                "FreeBusy unavailable (%s); assuming all slots free for %s", exc, date_str
            )
            return [c.strftime("%H:%M") for c in candidates]

        free: list[str] = []
        for start in candidates:
            end = start + timedelta(hours=SLOT_HOURS)
            overlaps = any(
                busy_start < end and start < busy_end for busy_start, busy_end in busy
            )
            if not overlaps:
                free.append(start.strftime("%H:%M"))
        return free


google_calendar_service = GoogleCalendarService()
