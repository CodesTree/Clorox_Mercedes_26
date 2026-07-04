from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas import BookingIn, BookingOut
from app.db import get_session
from app.services.booking import SharedCalendarDispatcher, create_booking as persist_booking
from app.services.google_calendar import google_calendar_service

router = APIRouter(tags=["booking"])

booking_dispatcher = SharedCalendarDispatcher(google_calendar_service)

@router.post("/booking", response_model=BookingOut)
def create_booking(
    booking: BookingIn,
    session: Session = Depends(get_session),
) -> BookingOut:
    return persist_booking(session=session, booking_in=booking, dispatcher=booking_dispatcher)
