"""Pydantic models for the AssetIQ REST contract (spec 00, section 3).

All monetary values are RM integers. Phase 03 implements the endpoints;
Phase 04 generates TS types from the OpenAPI these models produce.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str
    version: str


class VehicleProfileIn(BaseModel):
    model: str
    year: int = Field(ge=1970, le=2100)
    mileage: int = Field(ge=0)
    transmission: str
    fuel_type: str
    engine_size: float = Field(ge=0)
    mpg: float | None = None
    tax: float | None = None
    service_history_count: int | None = Field(default=None, ge=0)
    service_history_total: int | None = Field(default=None, ge=0)


class VehicleProfileOut(VehicleProfileIn):
    model_config = {"from_attributes": True}

    id: int
    name: str
    workshop: str | None = None
    glb_asset: str | None = None
    service_history_max: int | None = None
    created_at: datetime
    updated_at: datetime


class PredictOut(BaseModel):
    value_rm: int
    low_rm: int
    high_rm: int
    confidence: float = Field(ge=0, le=1)
    currency: Literal["RM"] = "RM"


class MarketListingOut(BaseModel):
    model_config = {"from_attributes": True}

    source: Literal["mudah", "carlist"]
    listing_url: str
    model: str
    variant: str | None = None
    year: int
    price_rm: int
    mileage: int | None = None
    location: str | None = None
    posted_at: str | None = None  # ISO-8601 YYYY-MM-DD


class MarketCompsOut(BaseModel):
    comps: list[MarketListingOut]
    median_rm: int | None
    delta_pct: float | None
    n: int


class DepreciationPoint(BaseModel):
    year: int
    value_rm: int
    retained_pct: float


class DepreciationOut(BaseModel):
    points: list[DepreciationPoint]


class ObdSnapshotOut(BaseModel):
    rpm: int
    coolant_c: float
    battery_v: float
    health: int = Field(ge=0, le=100)
    odo_km: int
    simulated: Literal[True] = True
    ts: datetime


class FaultOut(BaseModel):
    code: str
    description: str
    severity: str
    system: str


class FaultsOut(BaseModel):
    faults: list[FaultOut]


class BookingIn(BaseModel):
    profile_id: int
    name: str
    workshop: str
    car_model: str
    purpose: str
    date: str  # ISO-8601 YYYY-MM-DD
    time: str  # HH:MM (24h)


class BookingOut(BaseModel):
    booking_id: int
    status: str
    dispatched: bool
    dry_run: bool
    payload: dict[str, Any] | None = None
