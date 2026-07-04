from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas import FaultsOut
from app.db import get_session
from app.services.odx_service import OdxFaultService

router = APIRouter(tags=["diagnostics"])

odx_service = OdxFaultService()

@router.get("/odx/faults", response_model=FaultsOut)
def odx_faults(profile_id: int, session: Session = Depends(get_session)) -> FaultsOut:
    return FaultsOut(faults=odx_service.list_faults(session))
