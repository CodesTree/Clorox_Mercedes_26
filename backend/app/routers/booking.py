from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.orm import Booking as BookingRow
from app.schemas import (
    BookingAvailabilityOut,
    BookingDiagnosticsOut,
    BookingIn,
    BookingOut,
    BookingReplyOut,
)
from app.services import booking_agent, telegram_bot
from app.services.booking import SharedCalendarDispatcher, create_booking as persist_booking
from app.services.google_calendar import google_calendar_service

router = APIRouter(tags=["booking"])

# Fallback path (used only when Telegram is not configured): instant / dry-run
# calendar booking, preserving the previous behaviour.
booking_dispatcher = SharedCalendarDispatcher(google_calendar_service)


@router.get("/booking/diagnostics", response_model=BookingDiagnosticsOut)
def booking_diagnostics() -> BookingDiagnosticsOut:
    """Secret-free config check for the booking integrations.

    Reports which integrations are configured, the calendar being targeted, the
    service-account email to share the calendar with, and a live FreeBusy probe.
    """
    settings = get_settings()

    probe = "ok"
    try:
        now = datetime.now(timezone.utc)
        google_calendar_service.query_freebusy(now, now + timedelta(hours=1))
    except Exception as exc:  # noqa: BLE001 - surface any misconfig to the caller
        probe = f"error: {exc}"

    telegram_configured = telegram_bot.is_configured()
    webhook_info = telegram_bot.get_webhook_info() if telegram_configured else None
    webhook_result = webhook_info.get("result") if isinstance(webhook_info, dict) else None
    webhook_url = webhook_result.get("url") if isinstance(webhook_result, dict) else ""

    return BookingDiagnosticsOut(
        telegram_configured=telegram_configured,
        telegram_webhook_configured=bool(webhook_url),
        gemini_configured=bool(settings.gemini_api_key.strip()),
        calendar_write_configured=google_calendar_service.configured,
        calendar_read_configured=google_calendar_service.read_configured,
        calendar_id=settings.google_calendar_id,
        service_account_email=google_calendar_service.service_account_email(),
        freebusy_probe=probe,
    )


@router.get("/booking/availability", response_model=BookingAvailabilityOut)
def booking_availability(
    date: str = Query(..., description="ISO-8601 date, YYYY-MM-DD"),
) -> BookingAvailabilityOut:
    """Free working-hours slots for the date, from Google Calendar FreeBusy.

    Falls back to all working-hours slots when the calendar read is unconfigured.
    """
    slots = google_calendar_service.free_slots_for_date(date)
    return BookingAvailabilityOut(date=date, slots=slots)


@router.post("/booking", response_model=BookingOut)
def create_booking(
    booking: BookingIn,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> BookingOut:
    # Gated primary: when Telegram is configured, propose and wait for a human
    # reply before the calendar is written.
    if telegram_bot.is_configured():
        booking_row = BookingRow(
            profile_id=booking.profile_id,
            name=booking.name,
            workshop=booking.workshop,
            car_model=booking.car_model,
            purpose=booking.purpose,
            date=booking.date,
            time=booking.time,
            status="pending",
            negotiation_round=0,
        )
        session.add(booking_row)
        session.commit()
        session.refresh(booking_row)

        booking_row = booking_agent.dispatch_proposal(session, booking_row)

        dry_run = booking_row.status == "dry_run"
        return BookingOut(
            booking_id=booking_row.id,
            status=booking_row.status,
            dispatched=booking_row.status == "sent",
            dry_run=dry_run,
            payload=(
                None
                if dry_run
                else {"telegram_message_id": booking_row.telegram_message_id}
            ),
        )

    # Fallback: no Telegram configured -> instant / dry-run calendar flow.
    return persist_booking(
        session=session, booking_in=booking, dispatcher=booking_dispatcher
    )


@router.post("/booking/{booking_id}/check-reply", response_model=BookingReplyOut)
def check_booking_reply(
    booking_id: int,
    session: Session = Depends(get_session),
) -> BookingReplyOut:
    """On-demand poll: pull the latest Telegram reply and advance the booking."""
    booking_row = session.get(BookingRow, booking_id)
    if booking_row is None:
        raise HTTPException(status_code=404, detail=f"booking {booking_id} not found")
    return booking_agent.process_reply(session, booking_row)
