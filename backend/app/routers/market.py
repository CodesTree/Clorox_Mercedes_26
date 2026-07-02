from fastapi import APIRouter, HTTPException

from app.schemas import MarketCompsOut

router = APIRouter(tags=["market"])


@router.get("/market/comps", response_model=MarketCompsOut)
def market_comps(model: str, year: int | None = None, limit: int = 20) -> MarketCompsOut:
    raise HTTPException(
        status_code=503,
        detail="Not implemented in foundation - Phase 03 provides this from scraped market_listings.",
    )
