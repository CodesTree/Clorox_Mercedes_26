from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.schemas import AdvisoryInterpretOut
from app.services.advisory import ADVISORY_HORIZON_YEARS, build_advisory_interpretation
from app.services.gemini_summary import GeminiSummaryClient
from app.services.predictor import ModelUnavailable, PredictorService
from app.services.vehicle import ProfileNotFound, get_profile

router = APIRouter(tags=["advisory"])

predictor_service = PredictorService()
settings = get_settings()
summary_client = GeminiSummaryClient(
    api_key=settings.gemini_api_key,
    model=settings.gemini_model,
)


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
            summary_client=summary_client,
            horizon_years=ADVISORY_HORIZON_YEARS,
        )
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc
