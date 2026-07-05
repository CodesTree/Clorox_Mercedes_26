"""Engine/session wiring. DATABASE_URL is a secret — never log or echo it."""
from pathlib import Path

from sqlalchemy import inspect, text
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
    if _settings.database_url.startswith("sqlite"):
        _ensure_sqlite_compat_columns()


def _ensure_sqlite_compat_columns() -> None:
    inspector = inspect(engine)
    if "vehicle_profiles" not in inspector.get_table_names():
        return

    profile_cols = {c["name"] for c in inspector.get_columns("vehicle_profiles")}
    if "original_purchase_price_rm" not in profile_cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE vehicle_profiles ADD COLUMN original_purchase_price_rm INTEGER")
            )


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
