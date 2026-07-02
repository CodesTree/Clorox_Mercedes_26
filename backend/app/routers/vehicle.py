from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas import VehicleProfileIn, VehicleProfileOut
from app.db import get_session
from app.services.vehicle import ProfileNotFound, get_profile, to_schema, update_default_profile

router = APIRouter(tags=["vehicle"])


@router.get("/vehicle/profile", response_model=VehicleProfileOut)
def read_profile(id: int, session: Session = Depends(get_session)) -> VehicleProfileOut:
    try:
        return to_schema(get_profile(session, id))
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/vehicle/profile", response_model=VehicleProfileOut)
def put_profile(
    profile: VehicleProfileIn,
    session: Session = Depends(get_session),
) -> VehicleProfileOut:
    return to_schema(update_default_profile(session, profile))
