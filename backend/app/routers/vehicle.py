from fastapi import APIRouter, HTTPException

from app.schemas import VehicleProfileIn, VehicleProfileOut

router = APIRouter(tags=["vehicle"])

_NOT_IMPLEMENTED = "Not implemented in foundation - Phase 03 provides vehicle profiles."


@router.get("/vehicle/profile", response_model=VehicleProfileOut)
def get_profile(id: int) -> VehicleProfileOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)


@router.put("/vehicle/profile", response_model=VehicleProfileOut)
def put_profile(profile: VehicleProfileIn) -> VehicleProfileOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)
