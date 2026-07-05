from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app import orm
from app.schemas import BookingIn, BookingOut
from app.services.google_calendar import GoogleCalendarError, GoogleCalendarService


@dataclass(frozen=True)
class DispatchResult:
    status: str
    dispatched: bool
    dry_run: bool
    payload: dict


class BookingDispatcher(Protocol):
    def dispatch(self, booking: orm.Booking) -> DispatchResult:
        ...


class DryRunDispatcher:
    def dispatch(self, booking: orm.Booking) -> DispatchResult:
        payload = {
            "chat": "dry-run",
            "text": (
                "Inspection booking request\n"
                f"Name: {booking.name}\n"
                f"Nearest Mercedes Workshop: {booking.workshop}\n"
                f"Car model: {booking.car_model}\n"
                f"Purpose: {booking.purpose}\n"
                f"Date: {booking.date}\n"
                f"Time: {booking.time}"
            ),
        }
        return DispatchResult(status="dry_run", dispatched=False, dry_run=True, payload=payload)


class SharedCalendarDispatcher:
    def __init__(
        self,
        calendar_service: GoogleCalendarService,
        fallback: BookingDispatcher | None = None,
    ) -> None:
        self.calendar_service = calendar_service
        self.fallback = fallback or DryRunDispatcher()

    def dispatch(self, booking: orm.Booking) -> DispatchResult:
        config_error = self.calendar_service.configuration_error()
        if config_error is not None:
            result = self.fallback.dispatch(booking)
            result.payload["calendar_mode"] = "shared"
            result.payload["calendar_error"] = config_error
            return result

        try:
            event = self.calendar_service.create_booking_event(booking)
        except (GoogleCalendarError, Exception) as exc:
            result = self.fallback.dispatch(booking)
            result.payload["calendar_mode"] = "shared"
            result.payload["calendar_error"] = str(exc)
            return result

        booking.calendar_event_id = event.event_id
        return DispatchResult(
            status="booked",
            dispatched=True,
            dry_run=False,
            payload={
                "calendar_mode": "shared",
                "calendar_event_id": event.event_id,
                "calendar_html_link": event.html_link,
            },
        )


def create_booking(
    session: Session,
    booking_in: BookingIn,
    dispatcher: BookingDispatcher,
) -> BookingOut:
    booking = orm.Booking(
        profile_id=booking_in.profile_id,
        name=booking_in.name,
        workshop=booking_in.workshop,
        car_model=booking_in.car_model,
        purpose=booking_in.purpose,
        date=booking_in.date,
        time=booking_in.time,
        status="pending",
    )
    session.add(booking)
    session.commit()
    session.refresh(booking)

    result = dispatcher.dispatch(booking)
    booking.status = result.status
    session.commit()
    session.refresh(booking)

    return BookingOut(
        booking_id=booking.id,
        status=booking.status,
        dispatched=result.dispatched,
        dry_run=result.dry_run,
        payload=result.payload,
    )
