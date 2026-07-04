"""SQLAlchemy tables — the single SQLite schema (spec 00, section 2)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TrainingData(Base):
    """Cleaned merc.csv rows; prices already converted to RM by ml/ingest.py."""

    __tablename__ = "training_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String, index=True)
    year: Mapped[int]
    age: Mapped[int]
    price_rm: Mapped[int]
    transmission: Mapped[str]
    mileage: Mapped[int]
    fuel_type: Mapped[str]
    tax: Mapped[float]
    mpg: Mapped[float]
    engine_size: Mapped[float]
    source: Mapped[str] = mapped_column(String, default="merc.csv")
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MarketListing(Base):
    """Real scraped listings (Mercedes only); never synthetic rows."""

    __tablename__ = "market_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str]  # 'mudah' | 'carlist'
    listing_url: Mapped[str] = mapped_column(String, unique=True, index=True)
    model: Mapped[str] = mapped_column(String, index=True)
    variant: Mapped[str | None]
    year: Mapped[int]
    price_rm: Mapped[int]
    mileage: Mapped[int | None]
    transmission: Mapped[str | None]
    fuel_type: Mapped[str | None]
    location: Mapped[str | None]
    seller_type: Mapped[str] = mapped_column(String, default="unknown")  # dealer|private|unknown
    posted_at: Mapped[str | None]  # ISO-8601 YYYY-MM-DD, normalised at scrape time
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VehicleSpec(Base):
    """Approved technical vehicle specs; never merged into training_data."""

    __tablename__ = "vehicle_specs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String, default="ultimatespecs")
    source_url: Mapped[str] = mapped_column(String, unique=True, index=True)
    make: Mapped[str]
    model: Mapped[str] = mapped_column(String, index=True)
    variant: Mapped[str | None]
    generation: Mapped[str | None]
    year_start: Mapped[int | None]
    year_end: Mapped[int | None]
    specific_model: Mapped[str]
    engine_type: Mapped[str | None]
    engine_cc: Mapped[int | None]
    engine_aspiration: Mapped[str | None]
    transmission: Mapped[str | None]
    number_of_gears: Mapped[int | None]
    top_speed_kmh: Mapped[int | None]
    front_brakes: Mapped[str | None]
    rear_brakes: Mapped[str | None]
    front_suspension: Mapped[str | None]
    rear_suspension: Mapped[str | None]
    boot_space_litres: Mapped[int | None]
    seat_capacity: Mapped[int | None]
    number_of_doors: Mapped[int | None]
    torque_nm: Mapped[int | None]
    zero_to_100_kmh_s: Mapped[float | None]
    fuel_type: Mapped[str | None]
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VehicleProfile(Base):
    """The subject car being valued. `model` must be a canonical training class (enforced in P03)."""

    __tablename__ = "vehicle_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    model: Mapped[str]
    year: Mapped[int]
    mileage: Mapped[int]
    transmission: Mapped[str]
    fuel_type: Mapped[str]
    engine_size: Mapped[float]
    service_history_count: Mapped[int] = mapped_column(default=0)
    service_history_total: Mapped[int] = mapped_column(default=0)
    service_history_max: Mapped[int] = mapped_column(default=0)
    workshop: Mapped[str | None]
    glb_asset: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("vehicle_profiles.id"))
    name: Mapped[str]
    workshop: Mapped[str]
    car_model: Mapped[str]
    purpose: Mapped[str]
    date: Mapped[str]  # ISO-8601 YYYY-MM-DD
    time: Mapped[str]  # HH:MM (24h)
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # pending|sent|confirmed|booked|failed|dry_run
    telegram_message_id: Mapped[str | None]
    calendar_event_id: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class DtcCode(Base):
    """Cache of ODX-parsed fault-code definitions (source: real ODX files only)."""

    __tablename__ = "dtc_codes"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str]
    severity: Mapped[str]
    system: Mapped[str]
    source_odx: Mapped[str]
