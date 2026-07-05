from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.orm import Booking as BookingRow
from app.schemas import BookingIn, BookingOut
from app.services.telegram_bot import TelegramDispatcher

router = APIRouter(tags=["booking"])


@router.post("/booking", response_model=BookingOut)
def create_booking(
    booking: BookingIn,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> BookingOut:
    booking_row = BookingRow(
        profile_id=booking.profile_id,
        name=booking.name,
        workshop=booking.workshop,
        car_model=booking.car_model,
        purpose=booking.purpose,
        date=booking.date,
        time=booking.time,
        status="pending",
    )
    session.add(booking_row)
    session.commit()
    session.refresh(booking_row)

    dispatcher = TelegramDispatcher(session=session, background_tasks=background_tasks)
    result = dispatcher.dispatch(booking_row)

    return BookingOut(
        booking_id=booking_row.id,
        status=booking_row.status,
        dispatched=not result.dry_run and result.status != "dry_run",
        dry_run=result.dry_run,
    )
