# TEMP: replace with Phase 03's real protocol import once merged
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class BookingRecord(Protocol):
    id: int
    profile_id: int
    name: str
    workshop: str
    car_model: str
    purpose: str
    date: str
    time: str
    status: str
    telegram_message_id: str | None
    calendar_event_id: str | None
    created_at: datetime
    updated_at: datetime


class DispatchResult(Protocol):
    status: str
    telegram_message_id: str | None
    calendar_event_id: str | None
    dry_run: bool


class BookingDispatcher(Protocol):
    def dispatch(self, booking: BookingRecord) -> DispatchResult:
        ...