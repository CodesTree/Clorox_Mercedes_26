from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.schemas import MarketCompsOut
from app.db import get_session
from app.services.market import DEFAULT_LIMIT, get_market_comps
from app.services.predictor import ModelUnavailable, PredictorService
from app.services.vehicle import ensure_default_profile

router = APIRouter(tags=["market"])

predictor_service = PredictorService()


@router.get("/market/comps", response_model=MarketCompsOut)
def market_comps(
    model: str,
    year: int | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=100),
    session: Session = Depends(get_session),
) -> MarketCompsOut:
    predict_value_rm = None
    profile = ensure_default_profile(session)
    if profile.model == model:
        try:
            predict_value_rm = predictor_service.predict(profile).value_rm
        except ModelUnavailable:
            predict_value_rm = None
    return get_market_comps(
        session=session,
        model=model,
        year=year,
        limit=limit,
        predict_value_rm=predict_value_rm,
    )
