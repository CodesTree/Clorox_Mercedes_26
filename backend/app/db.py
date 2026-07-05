"""Engine/session wiring. DATABASE_URL is a secret — never log or echo it."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

_settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(_settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create the data directory (for on-disk SQLite) and all tables."""
    from app import orm

    if _settings.database_url.startswith("sqlite:///"):
        db_path = Path(_settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    orm.Base.metadata.create_all(bind=engine)
    _ensure_booking_columns()


def _ensure_booking_columns() -> None:
    """Idempotently add columns introduced after the demo DB was committed.

    `create_all` never ALTERs an existing table, so a checked-in SQLite file
    would otherwise be missing newer columns. Safe to run on every startup.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    try:
        columns = {col["name"] for col in inspector.get_columns("bookings")}
    except Exception:
        return

    if "negotiation_round" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE bookings ADD COLUMN negotiation_round INTEGER DEFAULT 0")
            )

    if "telegram_update_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE bookings ADD COLUMN telegram_update_id INTEGER"))


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
