from fastapi import APIRouter, HTTPException

from app.schemas import DepreciationOut, PredictOut, VehicleProfileIn

router = APIRouter(tags=["valuation"])

_NOT_IMPLEMENTED = "Not implemented in foundation - Phase 03 provides this. Train the model first: python -m ml.train"


@router.post("/predict", response_model=PredictOut)
def predict(profile: VehicleProfileIn) -> PredictOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)


@router.get("/depreciation", response_model=DepreciationOut)
def depreciation(profile_id: int, years: int = 5) -> DepreciationOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)
