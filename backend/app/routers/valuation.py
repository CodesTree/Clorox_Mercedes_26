from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas import CarFeaturesIn, DepreciationOut, PredictOut, VehicleProfileIn
from app.db import get_session
from app.services.predictor import ModelUnavailable, PredictorService
from app.services.price_predictor import PriceModelPredictor, PriceModelUnavailable
from app.services.vehicle import ProfileNotFound, get_profile

router = APIRouter(tags=["valuation"])

predictor_service = PredictorService()
price_model_predictor = PriceModelPredictor()


@router.post("/predict", response_model=PredictOut)
def predict(profile: VehicleProfileIn) -> PredictOut:
    try:
        return predictor_service.predict(profile)
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc


@router.post("/predict/obd", response_model=PredictOut)
def predict_obd(features: CarFeaturesIn) -> PredictOut:
    """Predict resale price + confidence from a mock OBD-II + car-specs payload.

    Uses the RandomForest artifact from 03_modeling.ipynb; confidence and [low, high]
    come from the calibrated per-tree prediction spread.
    """
    try:
        return price_model_predictor.predict(features.model_dump())
    except PriceModelUnavailable as exc:
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
