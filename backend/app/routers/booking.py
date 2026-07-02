from fastapi import APIRouter, HTTPException

from app.schemas import BookingIn, BookingOut

router = APIRouter(tags=["booking"])


@router.post("/booking", response_model=BookingOut)
def create_booking(booking: BookingIn) -> BookingOut:
    raise HTTPException(
        status_code=503,
        detail="Not implemented in foundation - Phase 03 wires the BookingDispatcher (dry-run without keys).",
    )
