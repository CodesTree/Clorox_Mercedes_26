from fastapi import APIRouter

from app.schemas import AdvisoryVoiceRequest, AdvisoryVoiceResponse
from app.services.advisory_voice import AdvisoryVoiceService

router = APIRouter(prefix="/advisory", tags=["advisory"])

advisory_voice_service = AdvisoryVoiceService()


@router.post("/voice/respond", response_model=AdvisoryVoiceResponse)
def respond_to_voice_advisory(payload: AdvisoryVoiceRequest) -> AdvisoryVoiceResponse:
    return advisory_voice_service.respond(payload.question, payload.advisory)
