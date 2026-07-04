from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas import DepreciationOut, PredictOut, VehicleProfileIn
from app.db import get_session
from app.services.predictor import ModelUnavailable, PredictorService
from app.services.vehicle import ProfileNotFound, get_profile

router = APIRouter(tags=["valuation"])

predictor_service = PredictorService()


@router.post("/predict", response_model=PredictOut)
def predict(profile: VehicleProfileIn) -> PredictOut:
    try:
        return predictor_service.predict(profile)
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc


@router.get("/depreciation", response_model=DepreciationOut)
def depreciation(
    profile_id: int,
    years: int = Query(default=5, ge=1, le=7),
    session: Session = Depends(get_session),
) -> DepreciationOut:
    try:
        profile = get_profile(session, profile_id)
        return predictor_service.depreciation(profile, years)
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc
