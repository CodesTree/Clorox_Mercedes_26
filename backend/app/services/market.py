from __future__ import annotations

from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import orm
from app.schemas import MarketCompsOut, MarketListingOut

DEFAULT_YEAR_WINDOW = 2
FALLBACK_YEAR_WINDOW = 5
MIN_TIGHT_COMPS = 3
DEFAULT_LIMIT = 20


def compute_delta_pct(predict_value_rm: int, median_rm: int) -> float | None:
    if median_rm <= 0:
        return None
    return round((predict_value_rm - median_rm) / median_rm, 4)


def _query_listings(
    session: Session,
    model: str,
    year: int | None,
    limit: int,
    year_window: int | None,
) -> list[orm.MarketListing]:
    stmt = select(orm.MarketListing).where(orm.MarketListing.model == model)
    if year is not None and year_window is not None:
        stmt = stmt.where(orm.MarketListing.year.between(year - year_window, year + year_window))
    stmt = stmt.order_by(orm.MarketListing.year.desc(), orm.MarketListing.price_rm.asc()).limit(limit)
    return list(session.scalars(stmt))


def get_market_comps(
    session: Session,
    model: str,
    year: int | None = None,
    limit: int = DEFAULT_LIMIT,
    predict_value_rm: int | None = None,
) -> MarketCompsOut:
    safe_limit = max(1, min(limit, 100))
    if year is None:
        listings = _query_listings(session, model, year, safe_limit, None)
    else:
        listings = _query_listings(session, model, year, safe_limit, DEFAULT_YEAR_WINDOW)
        if len(listings) < MIN_TIGHT_COMPS:
            listings = _query_listings(session, model, year, safe_limit, FALLBACK_YEAR_WINDOW)

    if not listings:
        return MarketCompsOut(comps=[], median_rm=None, delta_pct=None, n=0)

    median_rm = int(round(median([row.price_rm for row in listings])))
    delta_pct = (
        compute_delta_pct(predict_value_rm=predict_value_rm, median_rm=median_rm)
        if predict_value_rm is not None
        else None
    )
    return MarketCompsOut(
        comps=[MarketListingOut.model_validate(row) for row in listings],
        median_rm=median_rm,
        delta_pct=delta_pct,
        n=len(listings),
    )
