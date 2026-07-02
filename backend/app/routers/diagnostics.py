from fastapi import APIRouter, HTTPException

from app.schemas import FaultsOut

router = APIRouter(tags=["diagnostics"])


@router.get("/odx/faults", response_model=FaultsOut)
def odx_faults(profile_id: int) -> FaultsOut:
    raise HTTPException(
        status_code=503,
        detail="Not implemented in foundation - Phase 03 parses data/sample_odx via odxtools.",
    )
