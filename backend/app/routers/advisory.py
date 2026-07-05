from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import AdvisoryInterpretOut
from app.services.advisory import ADVISORY_HORIZON_YEARS, build_advisory_interpretation
from app.services.predictor import ModelUnavailable, PredictorService
from app.services.vehicle import ProfileNotFound, get_profile

router = APIRouter(tags=["advisory"])

predictor_service = PredictorService()


@router.get("/advisory/interpret", response_model=AdvisoryInterpretOut)
def advisory_interpret(
    profile_id: int,
    session: Session = Depends(get_session),
) -> AdvisoryInterpretOut:
    try:
        profile = get_profile(session, profile_id)
        return build_advisory_interpretation(
            profile=profile,
            predictor=predictor_service,
            horizon_years=ADVISORY_HORIZON_YEARS,
        )
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc
