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
    original_purchase_price_rm: int | None = Field(default=None, ge=0)
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


class CarFeaturesIn(BaseModel):
    """Full feature payload for the /predict/obd demo (mock OBD-II + car specs).

    Mirrors the columns the RF price model was trained on
    (see backend/ml/artifacts/price_model_meta.json). Numeric fields are floats so the
    demo JSON round-trips cleanly; the OBD-II block is the last six fields.
    """

    # --- car specs ---
    model_class: str
    year: float
    mileage: float
    transmission: str
    fuel_type: str
    engine_size: float
    source_market: str
    age: float
    variant: str
    displacement_cc: float
    n_cylinders: float
    n_gears: float
    top_speed_kmh: float
    torque_nm: float
    accel_0_100_s: float
    boot_l: float
    engine_config: str
    aspiration: str
    gear_type: str
    front_brake: str
    rear_brake: str
    match_level: str
    # --- simulated OBD-II / vehicle-health block ---
    battery_soh: float
    trans_adapt_offset: float
    estimated_annual_mileage: float
    dtc_fault_count: float
    brake_life_pct: float
    health_score: float


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


class RepairItemOut(BaseModel):
    name: str
    cost_rm: int = Field(ge=0)


class AdvisoryInterpretOut(BaseModel):
    recommendation: Literal["Sell", "Repair and keep"]
    summary: str
    horizon_years: int
    current_value_rm: int
    horizon_value_rm: int
    depreciation_loss_rm: int
    total_repair_cost_rm: int
    repairs: list[RepairItemOut]
    llm_used: bool = False


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
    # Canonical booking details so the UI shows the confirmed slot rather than
    # its own editable form state (which drifts on reschedule / modal reopen).
    name: str = ""
    workshop: str = ""
    car_model: str = ""
    date: str = ""
    time: str = ""


class BookingAvailabilityOut(BaseModel):
    date: str  # ISO-8601 YYYY-MM-DD
    slots: list[str]  # free "HH:MM" start times within working hours


class BookingReplyOut(BaseModel):
    booking_id: int
    status: str
    booked: bool
    proposed_date: str
    proposed_time: str
    workshop: str = ""
    round: int
    classification: str  # confirmed | unavailable | unclear | none
    message: str


class BookingDiagnosticsOut(BaseModel):
    """Secret-free view of booking-integration configuration for debugging."""

    telegram_configured: bool
    telegram_webhook_configured: bool
    gemini_configured: bool
    calendar_write_configured: bool
    calendar_read_configured: bool
    calendar_id: str
    service_account_email: str | None = None  # share the calendar with this address
    freebusy_probe: str  # "ok" or "error: <reason>"
