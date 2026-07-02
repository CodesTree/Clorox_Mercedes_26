# AssetIQ Phase 00 — Foundation & Shared Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the AssetIQ monorepo and freeze every shared contract (SQLite schema, REST/OpenAPI surface, `.env` keys) so Phases 01–05 can be built in parallel without collisions.

**Architecture:** A FastAPI backend (`backend/app`) exposes the full API contract as typed stub endpoints (503 "not implemented") so `/openapi.json` is the frozen source of truth from day one; SQLAlchemy ORM defines all five tables; a Vite/React/TS frontend renders a dark themed shell that proves connectivity via `/health` through a dev proxy. A real ODX sample file (odxtools' somersault example) is committed for Phase 03.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, pydantic-settings, pytest, httpx, odxtools · Node 22, Vite 6, React 18, TypeScript 5.7, vitest, openapi-typescript.

**Spec:** `docs/superpowers/specs/2026-07-02-assetiq-00-foundation-design.md`

## Decisions locked by this plan (resolves the spec's `TODO(P00)` items)

1. **Dependency pins:** exact versions in `backend/requirements.txt` + `frontend/package.json` (Task 1/9). Python 3.11 (installed: 3.11.2), Node 22. odxtools is installed from a bounded range, then frozen to the exact installed version.
2. **TS type generation:** `openapi-typescript` reads a committed `frontend/openapi.json` snapshot (dumped from the app, no server needed) → `frontend/src/types/api.d.ts` via `npm run gen:api` (Task 10).
3. **Sample ODX:** generate `data/sample_odx/somersault.pdx` from the official `mercedes-benz/odxtools` somersault example, pinned to the installed odxtools version (Task 8). Real example data, not hand-authored.
4. **`seller_type` / `posted_at`:** `seller_type ∈ {'dealer','private','unknown'}` (TEXT, default `'unknown'`); `posted_at` is an ISO-8601 `YYYY-MM-DD` TEXT column, normalised at scrape time (raw source format still confirmed at Gate 1).
5. **Working directory convention:** backend processes run from **repo root** (`uvicorn app.main:app --app-dir backend`) so `./data/` and `.env` resolve at root. Tests run from `backend/` and always override `DATABASE_URL` to a temp file via `conftest.py`.
6. **Dev scripts:** no Makefile (Windows host) — npm scripts in `frontend/`, documented commands in `README.md`.

---

### Task 0: Feature branch

**Files:** none (git only)

- [ ] **Step 1: Confirm clean main and create the branch**

```bash
cd "C:/Users/Chan Zheng Shao/OneDrive/Desktop/Github Repo/Clorox_Mercedes_26"
git checkout main && git pull && git status --short
git checkout -b feat/00-foundation
```

Expected: no uncommitted changes; branch `feat/00-foundation` created. (If the branch already exists from the planning commit, just `git checkout feat/00-foundation`.)

---

### Task 1: Backend package skeleton + pinned dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`, `backend/app/routers/__init__.py`, `backend/app/services/__init__.py`, `backend/ml/__init__.py`, `backend/scraper/__init__.py`, `backend/tests/__init__.py`
- Create: `backend/scraper/fixtures/.gitkeep`

- [ ] **Step 1: Create the directory tree and empty package files**

```bash
cd "C:/Users/Chan Zheng Shao/OneDrive/Desktop/Github Repo/Clorox_Mercedes_26"
mkdir -p backend/app/routers backend/app/services backend/ml backend/scraper/fixtures backend/tests data/sample_odx frontend
touch backend/app/__init__.py backend/app/routers/__init__.py backend/app/services/__init__.py \
      backend/ml/__init__.py backend/scraper/__init__.py backend/tests/__init__.py \
      backend/scraper/fixtures/.gitkeep
```

- [ ] **Step 2: Write `backend/requirements.txt`**

```
# Runtime
fastapi==0.115.8
uvicorn[standard]==0.34.0
sqlalchemy==2.0.38
pydantic==2.10.6
pydantic-settings==2.7.1
odxtools>=8,<11    # frozen to the exact installed version in Step 6

# Dev / test
pytest==8.3.4
httpx==0.28.1
```

> If pip reports any pinned version as not-found, bump to the nearest newer patch release and keep the file updated — the point is that the committed file holds exact, working pins.

- [ ] **Step 3: Write `backend/pyproject.toml`**

```toml
[project]
name = "assetiq-backend"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
```

- [ ] **Step 4: Create the venv and install**

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -r requirements.txt
```

Expected: all packages install without resolution errors.

- [ ] **Step 5: Verify imports**

```bash
.venv/Scripts/python -c "import fastapi, sqlalchemy, pydantic_settings, odxtools; print('imports ok')"
```

Expected: `imports ok`

- [ ] **Step 6: Freeze the odxtools pin**

```bash
.venv/Scripts/python -m pip show odxtools | grep -i ^version
```

Replace the `odxtools>=8,<11` line in `requirements.txt` with `odxtools==<that version>` (keep a comment `# pinned from range install`).

- [ ] **Step 7: Commit**

```bash
cd ..
git add backend
git commit -m "chore(00): backend package skeleton with pinned dependencies"
```

---

### Task 2: Settings (`config.py`), `.env.example`, `.gitignore`

**Files:**
- Create: `backend/app/config.py`
- Create: `.env.example`
- Modify: `.gitignore` (append)
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_config.py`:

```python
from app.config import Settings


def test_defaults_load_without_env_file():
    s = Settings(_env_file=None)
    assert s.database_url.startswith("sqlite:///")
    assert s.fx_gbp_to_rm > 0
    assert "http://localhost:5173" in s.cors_origin_list


def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("FX_GBP_TO_RM", "6.25")
    assert Settings(_env_file=None).fx_gbp_to_rm == 6.25


def test_cors_origins_splits_on_comma():
    s = Settings(_env_file=None, cors_origins="http://a.test, http://b.test")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend
.venv/Scripts/python -m pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Write `backend/app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from environment variables / .env.

    SECURITY: database_url and the phase-05 credentials are secrets.
    Never log, print, or return them from any endpoint.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite:///./data/assetiq.db"
    fx_gbp_to_rm: float = 5.90
    cors_origins: str = "http://localhost:5173"
    scraper_user_agent: str = "AssetIQResearchBot/0.1 (+contact)"
    scraper_rate_limit_seconds: float = 4.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    gemini_api_key: str = ""
    google_calendar_credentials_json: str = "./secrets/google_sa.json"
    google_calendar_id: str = "primary"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Write `.env.example` at repo root** (placeholders only — exactly as the spec)

```
DATABASE_URL=sqlite:///./data/assetiq.db
FX_GBP_TO_RM=5.90
CORS_ORIGINS=http://localhost:5173
SCRAPER_USER_AGENT=AssetIQResearchBot/0.1 (+contact)
SCRAPER_RATE_LIMIT_SECONDS=4
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
GEMINI_API_KEY=
GOOGLE_CALENDAR_CREDENTIALS_JSON=./secrets/google_sa.json
GOOGLE_CALENDAR_ID=primary
```

- [ ] **Step 6: Append to root `.gitignore`**

```
# --- AssetIQ project ---
.env
data/*.db
backend/ml/artifacts/
secrets/
backend/.venv/
node_modules/
frontend/dist/
```

- [ ] **Step 7: Commit**

```bash
cd ..
git add backend/app/config.py backend/tests/test_config.py .env.example .gitignore
git commit -m "feat(00): typed Settings from .env with committed placeholder example"
```

---

### Task 3: API contract schemas (`schemas.py`)

**Files:**
- Create: `backend/app/schemas.py`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_schemas.py`:

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app import schemas


def test_health_out():
    h = schemas.HealthOut(status="ok", version="0.1.0")
    assert h.status == "ok"


def test_vehicle_profile_in_minimal():
    p = schemas.VehicleProfileIn(
        model="SL CLASS", year=2016, mileage=42000, transmission="Automatic",
        fuel_type="Petrol", engine_size=5.5,
    )
    assert p.mpg is None and p.tax is None


def test_vehicle_profile_in_rejects_negative_mileage():
    with pytest.raises(ValidationError):
        schemas.VehicleProfileIn(
            model="SL CLASS", year=2016, mileage=-1, transmission="Automatic",
            fuel_type="Petrol", engine_size=5.5,
        )


def test_predict_out_currency_is_fixed_to_rm():
    out = schemas.PredictOut(value_rm=738000, low_rm=712000, high_rm=765000, confidence=0.92)
    assert out.currency == "RM"


def test_market_comps_out_allows_empty_market():
    out = schemas.MarketCompsOut(comps=[], median_rm=None, delta_pct=None, n=0)
    assert out.comps == []


def test_market_listing_source_is_constrained():
    with pytest.raises(ValidationError):
        schemas.MarketListingOut(
            source="ebay", listing_url="https://x.test/1", model="C Class",
            year=2018, price_rm=180000,
        )


def test_obd_snapshot_is_always_labelled_simulated():
    snap = schemas.ObdSnapshotOut(
        rpm=831, coolant_c=77.0, battery_v=12.6, health=87, odo_km=42000,
        ts=datetime.now(timezone.utc),
    )
    assert snap.simulated is True
    with pytest.raises(ValidationError):
        schemas.ObdSnapshotOut(
            rpm=831, coolant_c=77.0, battery_v=12.6, health=87, odo_km=42000,
            ts=datetime.now(timezone.utc), simulated=False,
        )


def test_depreciation_out():
    out = schemas.DepreciationOut(
        points=[schemas.DepreciationPoint(year=2026, value_rm=738000, retained_pct=1.0)]
    )
    assert out.points[0].retained_pct == 1.0


def test_faults_out():
    out = schemas.FaultsOut(
        faults=[schemas.FaultOut(code="P0301", description="d", severity="warn", system="engine")]
    )
    assert out.faults[0].code == "P0301"


def test_booking_roundtrip():
    b_in = schemas.BookingIn(
        profile_id=1, name="Chan", workshop="Hap Seng Star KL", car_model="SL CLASS",
        purpose="Certified inspection", date="2026-07-10", time="10:00",
    )
    b_out = schemas.BookingOut(booking_id=1, status="dry_run", dispatched=False, dry_run=True)
    assert b_in.workshop == "Hap Seng Star KL" and b_out.dry_run is True
```

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/Scripts/python -m pytest tests/test_schemas.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas'` (or `ImportError` on names).

- [ ] **Step 3: Write `backend/app/schemas.py`**

```python
"""Pydantic models for the AssetIQ REST contract (spec 00, section 3).

All monetary values are RM integers. Phase 03 implements the endpoints;
Phase 04 generates TS types from the OpenAPI these models produce.
"""
from datetime import datetime
from typing import Literal

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_schemas.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/app/schemas.py backend/tests/test_schemas.py
git commit -m "feat(00): freeze REST contract as Pydantic schemas"
```

---

### Task 4: ORM tables + engine (`orm.py`, `db.py`) and test conftest

**Files:**
- Create: `backend/app/orm.py`
- Create: `backend/app/db.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_orm.py`

- [ ] **Step 1: Write `backend/tests/conftest.py`** (must exist before any app-importing test so the real DB is never touched)

```python
"""Test bootstrap: force a throwaway SQLite file BEFORE any app import."""
import os
import tempfile
from pathlib import Path

_tmpdir = tempfile.mkdtemp(prefix="assetiq-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_tmpdir) / 'test.db').as_posix()}"
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_orm.py`:

```python
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app import orm

EXPECTED_TABLES = {
    "training_data",
    "market_listings",
    "vehicle_profiles",
    "bookings",
    "dtc_codes",
}


def test_all_five_tables_create_on_temp_sqlite(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'orm.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_listing_url_is_unique(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'uniq.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("market_listings")}
    assert "listing_url" in cols
    uniques = [u["column_names"] for u in inspect(engine).get_unique_constraints("market_listings")]
    indexes = [i["column_names"] for i in inspect(engine).get_indexes("market_listings") if i["unique"]]
    assert ["listing_url"] in uniques + indexes
```

- [ ] **Step 3: Run it to verify it fails**

```bash
.venv/Scripts/python -m pytest tests/test_orm.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.orm'`.

- [ ] **Step 4: Write `backend/app/orm.py`**

```python
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
```

- [ ] **Step 5: Write `backend/app/db.py`**

```python
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


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_orm.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
cd ..
git add backend/app/orm.py backend/app/db.py backend/tests/conftest.py backend/tests/test_orm.py
git commit -m "feat(00): SQLite schema (5 tables) and engine wiring"
```

---

### Task 5: FastAPI app with `/health` + CORS (`main.py`)

**Files:**
- Create: `backend/app/main.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_and_version():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_cors_allows_the_dev_frontend_origin():
    with TestClient(app) as client:
        resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/Scripts/python -m pytest tests/test_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Write `backend/app/main.py`** (no routers yet — Task 6 edits this file to register them)

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.schemas import HealthOut

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AssetIQ API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    return HealthOut(status="ok", version=app.version)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_health.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Boot check with uvicorn (from repo root)**

```bash
cd ..
backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000 &
sleep 3
curl -s http://localhost:8000/health
kill %1
```

Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_health.py
git commit -m "feat(00): FastAPI app boots with /health and CORS"
```

---

### Task 6: Contract stub routers (freeze `/openapi.json`)

**Files:**
- Create: `backend/app/routers/valuation.py`, `backend/app/routers/market.py`, `backend/app/routers/telemetry.py`, `backend/app/routers/diagnostics.py`, `backend/app/routers/vehicle.py`, `backend/app/routers/booking.py`
- Modify: `backend/app/main.py` (register routers)
- Test: `backend/tests/test_contract.py`

Every stub declares the real request/response models (so OpenAPI is complete and correct) and raises 503 with an actionable message. Phase 03 replaces the bodies; the signatures must not change.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_contract.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

EXPECTED_PATHS = {
    "/health": {"get"},
    "/predict": {"post"},
    "/market/comps": {"get"},
    "/depreciation": {"get"},
    "/obd/snapshot": {"get"},
    "/obd/stream": {"get"},
    "/odx/faults": {"get"},
    "/vehicle/profile": {"get", "put"},
    "/booking": {"post"},
}


def test_openapi_exposes_the_full_contract():
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
    for path, methods in EXPECTED_PATHS.items():
        assert path in spec["paths"], f"missing path: {path}"
        have = set(spec["paths"][path].keys())
        assert methods <= have, f"{path}: expected {methods}, got {have}"


def test_stubs_return_503_not_500():
    with TestClient(app) as client:
        assert client.get("/market/comps", params={"model": "SL CLASS"}).status_code == 503
        assert client.get("/obd/snapshot", params={"profile_id": 1}).status_code == 503
        assert client.get("/odx/faults", params={"profile_id": 1}).status_code == 503
        assert client.get("/vehicle/profile", params={"id": 1}).status_code == 503
        assert client.get("/depreciation", params={"profile_id": 1}).status_code == 503
        body = {
            "model": "SL CLASS", "year": 2016, "mileage": 42000,
            "transmission": "Automatic", "fuel_type": "Petrol", "engine_size": 5.5,
        }
        assert client.post("/predict", json=body).status_code == 503


def test_validation_still_applies_to_stubs():
    with TestClient(app) as client:
        resp = client.post("/predict", json={"model": "SL CLASS"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend
.venv/Scripts/python -m pytest tests/test_contract.py -v
```

Expected: FAIL — missing paths in openapi.

- [ ] **Step 3: Write the six routers**

`backend/app/routers/valuation.py`:

```python
from fastapi import APIRouter, HTTPException

from app.schemas import DepreciationOut, PredictOut, VehicleProfileIn

router = APIRouter(tags=["valuation"])

_NOT_IMPLEMENTED = "Not implemented in foundation — Phase 03 provides this. Train the model first: python -m ml.train"


@router.post("/predict", response_model=PredictOut)
def predict(profile: VehicleProfileIn) -> PredictOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)


@router.get("/depreciation", response_model=DepreciationOut)
def depreciation(profile_id: int, years: int = 5) -> DepreciationOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)
```

`backend/app/routers/market.py`:

```python
from fastapi import APIRouter, HTTPException

from app.schemas import MarketCompsOut

router = APIRouter(tags=["market"])


@router.get("/market/comps", response_model=MarketCompsOut)
def market_comps(model: str, year: int | None = None, limit: int = 20) -> MarketCompsOut:
    raise HTTPException(
        status_code=503,
        detail="Not implemented in foundation — Phase 03 provides this from scraped market_listings.",
    )
```

`backend/app/routers/telemetry.py`:

```python
from fastapi import APIRouter, HTTPException

from app.schemas import ObdSnapshotOut

router = APIRouter(tags=["telemetry"])

_NOT_IMPLEMENTED = "Not implemented in foundation — Phase 03 provides the simulated OBD-II service."


@router.get("/obd/snapshot", response_model=ObdSnapshotOut)
def obd_snapshot(profile_id: int) -> ObdSnapshotOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)


@router.get("/obd/stream")
def obd_stream(profile_id: int):
    """SSE stream of ObdSnapshotOut payloads (implemented in Phase 03)."""
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)
```

`backend/app/routers/diagnostics.py`:

```python
from fastapi import APIRouter, HTTPException

from app.schemas import FaultsOut

router = APIRouter(tags=["diagnostics"])


@router.get("/odx/faults", response_model=FaultsOut)
def odx_faults(profile_id: int) -> FaultsOut:
    raise HTTPException(
        status_code=503,
        detail="Not implemented in foundation — Phase 03 parses data/sample_odx via odxtools.",
    )
```

`backend/app/routers/vehicle.py`:

```python
from fastapi import APIRouter, HTTPException

from app.schemas import VehicleProfileIn, VehicleProfileOut

router = APIRouter(tags=["vehicle"])

_NOT_IMPLEMENTED = "Not implemented in foundation — Phase 03 provides vehicle profiles."


@router.get("/vehicle/profile", response_model=VehicleProfileOut)
def get_profile(id: int) -> VehicleProfileOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)


@router.put("/vehicle/profile", response_model=VehicleProfileOut)
def put_profile(profile: VehicleProfileIn) -> VehicleProfileOut:
    raise HTTPException(status_code=503, detail=_NOT_IMPLEMENTED)
```

`backend/app/routers/booking.py`:

```python
from fastapi import APIRouter, HTTPException

from app.schemas import BookingIn, BookingOut

router = APIRouter(tags=["booking"])


@router.post("/booking", response_model=BookingOut)
def create_booking(booking: BookingIn) -> BookingOut:
    raise HTTPException(
        status_code=503,
        detail="Not implemented in foundation — Phase 03 wires the BookingDispatcher (dry-run without keys).",
    )
```

- [ ] **Step 4: Register routers in `backend/app/main.py`** — add below the CORS middleware block:

```python
from app.routers import booking, diagnostics, market, telemetry, valuation, vehicle

app.include_router(valuation.router)
app.include_router(market.router)
app.include_router(telemetry.router)
app.include_router(diagnostics.router)
app.include_router(vehicle.router)
app.include_router(booking.router)
```

(Keep the import at the top of the file with the other imports.)

- [ ] **Step 5: Run the full backend suite**

```bash
.venv/Scripts/python -m pytest -v
```

Expected: all tests pass (config 3, schemas 10, orm 2, health 2, contract 3).

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/app/routers backend/app/main.py backend/tests/test_contract.py
git commit -m "feat(00): freeze full REST contract as typed 503 stubs in openapi.json"
```

---

### Task 7: Secret-safety test

**Files:**
- Test: `backend/tests/test_secret_safety.py`

- [ ] **Step 1: Write the test** (this is a spec invariant, not TDD of new code — it must pass immediately against the existing app)

`backend/tests/test_secret_safety.py`:

```python
"""Spec invariant: the DB connection string never appears in responses or logs."""
import logging

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_database_url_never_leaks_into_responses_or_logs(caplog):
    secret = get_settings().database_url
    assert secret  # sanity: we are actually testing something

    with caplog.at_level(logging.DEBUG):
        with TestClient(app) as client:
            health_text = client.get("/health").text
            openapi_text = client.get("/openapi.json").text
            error_text = client.get("/market/comps", params={"model": "X"}).text

    assert secret not in health_text
    assert secret not in openapi_text
    assert secret not in error_text
    assert secret not in caplog.text
```

- [ ] **Step 2: Run it — it must pass**

```bash
cd backend
.venv/Scripts/python -m pytest tests/test_secret_safety.py -v
```

Expected: 1 passed. If it fails, a leak exists — find and remove the leak; do not weaken the test.

- [ ] **Step 3: Commit**

```bash
cd ..
git add backend/tests/test_secret_safety.py
git commit -m "test(00): assert DATABASE_URL never leaks into responses or logs"
```

---

### Task 8: Real sample ODX file (`data/sample_odx/somersault.pdx`)

**Files:**
- Create: `data/sample_odx/somersault.pdx` (generated, committed)
- Create: `data/sample_odx/README.md`
- Test: `backend/tests/test_sample_odx.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_sample_odx.py`:

```python
from pathlib import Path

import odxtools

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_odx" / "somersault.pdx"


def test_sample_pdx_exists_and_loads():
    assert SAMPLE.exists(), "generate it: see data/sample_odx/README.md"
    db = odxtools.load_pdx_file(str(SAMPLE))
    assert len(db.diag_layers) > 0
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend
.venv/Scripts/python -m pytest tests/test_sample_odx.py -v
```

Expected: FAIL — assertion on `SAMPLE.exists()`.

- [ ] **Step 3: Generate the PDX from the official odxtools example, pinned to the installed version**

```bash
REPO="C:/Users/Chan Zheng Shao/OneDrive/Desktop/Github Repo/Clorox_Mercedes_26"
WORK=$(mktemp -d)   # any throwaway dir outside the repo works
ODXVER=$("$REPO/backend/.venv/Scripts/python" -m pip show odxtools | grep -i ^version | cut -d' ' -f2)
cd "$WORK"
git clone --depth 1 --branch "$ODXVER" https://github.com/mercedes-benz/odxtools odxtools-src \
  || git clone --depth 1 https://github.com/mercedes-benz/odxtools odxtools-src
head -40 odxtools-src/examples/mksomersaultpdx.py   # confirm its CLI: expected to take the output path
"$REPO/backend/.venv/Scripts/python" odxtools-src/examples/mksomersaultpdx.py \
  "$REPO/data/sample_odx/somersault.pdx"
```

> If the example script's API doesn't match the installed odxtools version (import errors), install the cloned source into a throwaway venv and run it there — the output PDX is version-independent data. Adjust the invocation to whatever `head -40` shows; the intent is fixed: produce the official somersault example PDX.

- [ ] **Step 4: Inspect what was generated (record DTC count for Phase 03)**

```bash
cd "<repo>/backend"
.venv/Scripts/python - <<'PY'
import odxtools
db = odxtools.load_pdx_file("../data/sample_odx/somersault.pdx")
print("diag layers:", [dl.short_name for dl in db.diag_layers])
n = 0
for dl in db.diag_layers:
    spec = getattr(dl, "diag_data_dictionary_spec", None)
    for dop in (getattr(spec, "dtc_dops", None) or []):
        n += len(dop.dtcs)
print("DTC definitions:", n)
PY
```

Expected: at least one diag layer; note the DTC count in the commit message.

- [ ] **Step 5: Run the test to verify it passes**

```bash
.venv/Scripts/python -m pytest tests/test_sample_odx.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Write `data/sample_odx/README.md`**

```markdown
# Sample ODX data

`somersault.pdx` is the official example ECU dataset from
[mercedes-benz/odxtools](https://github.com/mercedes-benz/odxtools), generated with
`examples/mksomersaultpdx.py` at the version pinned in `backend/requirements.txt`.

It is real ODX example data (not hand-authored) and is what Phase 03's `/odx/faults`
parses via `odxtools.load_pdx_file`. Regenerate with the same script if the odxtools
pin changes.
```

- [ ] **Step 7: Commit**

```bash
cd ..
git add data/sample_odx backend/tests/test_sample_odx.py
git commit -m "feat(00): commit real odxtools somersault example PDX for Phase 03"
```

---

### Task 9: Frontend shell (Vite + React + TS, themed, calls `/health`)

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `frontend/src/styles/theme.css`, `frontend/src/vite-env.d.ts`, `frontend/src/test-setup.ts`
- Create: `frontend/public/models/README.md`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "assetiq-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "gen:api": "openapi-typescript openapi.json -o src/types/api.d.ts"
  },
  "dependencies": {
    "@react-three/drei": "9.120.4",
    "@react-three/fiber": "8.17.10",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "three": "0.172.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "6.6.3",
    "@testing-library/react": "16.2.0",
    "@types/react": "18.3.18",
    "@types/react-dom": "18.3.5",
    "@types/three": "0.172.0",
    "@vitejs/plugin-react": "4.3.4",
    "@playwright/test": "1.49.1",
    "jsdom": "26.0.0",
    "msw": "2.7.0",
    "openapi-typescript": "7.5.2",
    "typescript": "5.7.3",
    "vite": "6.0.7",
    "vitest": "2.1.8"
  }
}
```

> If `npm install` reports a version that doesn't exist, bump to the nearest available patch release and keep package.json updated — committed pins must be exact and working.

- [ ] **Step 2: Write `frontend/vite.config.ts`**

```ts
/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test-setup.ts"],
  },
});
```

- [ ] **Step 3: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Write `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AssetIQ — Mercedes-Benz Resale Intelligence</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write the source files**

`frontend/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

`frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

`frontend/src/api/client.ts`:

```ts
// Dev traffic goes through the Vite proxy (/api -> http://localhost:8000).
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export interface HealthOut {
  status: string;
  version: string;
}

export async function getHealth(): Promise<HealthOut> {
  const resp = await fetch(`${API_BASE}/health`);
  if (!resp.ok) throw new Error(`health check failed: ${resp.status}`);
  return resp.json();
}
```

`frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from "react";
import { getHealth } from "./api/client";
import "./styles/theme.css";

type ApiStatus = "checking" | "online" | "offline";

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [version, setVersion] = useState("");

  useEffect(() => {
    getHealth()
      .then((h) => {
        setApiStatus("online");
        setVersion(h.version);
      })
      .catch(() => setApiStatus("offline"));
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <span className="wordmark">
          <span className="wordmark-spark">✦</span> AssetIQ
          <span className="wordmark-sub">for Mercedes-Benz</span>
        </span>
        <span className={`api-pill api-pill--${apiStatus}`} data-testid="api-status">
          {apiStatus === "checking"
            ? "Connecting…"
            : apiStatus === "online"
              ? `API online · v${version}`
              : "API offline"}
        </span>
      </header>
      <section className="stage">
        <p className="stage-placeholder">3D stage — Phase 04</p>
      </section>
    </main>
  );
}
```

`frontend/src/styles/theme.css` (baseline tokens — final design tokens are `TODO(P04)`):

```css
:root {
  --bg: #0a0f0e;
  --surface: #101615;
  --line: #1d2624;
  --text: #e8efed;
  --text-dim: #8fa39e;
  --accent: #2fe6c8;
  --danger: #e66a6a;
  --font-ui: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

* { box-sizing: border-box; margin: 0; }
html, body, #root { height: 100%; }
body { background: var(--bg); color: var(--text); font-family: var(--font-ui); }

.shell { display: flex; flex-direction: column; height: 100%; }
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; border-bottom: 1px solid var(--line);
}
.wordmark { font-weight: 600; letter-spacing: 0.04em; }
.wordmark-spark { color: var(--accent); }
.wordmark-sub {
  margin-left: 8px; font-size: 11px; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.12em;
}
.api-pill {
  font-family: var(--font-mono); font-size: 12px; padding: 4px 12px;
  border-radius: 999px; border: 1px solid var(--line); color: var(--text-dim);
}
.api-pill--online { color: var(--accent); border-color: var(--accent); }
.api-pill--offline { color: var(--danger); border-color: var(--danger); }
.stage { flex: 1; display: grid; place-items: center; }
.stage-placeholder {
  color: var(--text-dim); font-family: var(--font-mono); font-size: 13px;
  letter-spacing: 0.08em; text-transform: uppercase;
}
```

`frontend/src/test-setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

`frontend/public/models/README.md`:

```markdown
# 3D model drop-zone

Place the pre-rendered Mercedes AMG GT model here as a `.glb` file. If this folder
contains no `.glb`, the app renders a procedural low-poly coupe fallback (Phase 04).
```

- [ ] **Step 6: Write the failing smoke test**

`frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok", version: "0.1.0" }),
    }),
  );
});

test("renders the AssetIQ shell and reports API status", async () => {
  render(<App />);
  expect(screen.getByText(/AssetIQ/)).toBeInTheDocument();
  expect(await screen.findByTestId("api-status")).toHaveTextContent(/API online · v0.1.0/);
});
```

- [ ] **Step 7: Install and run the test**

```bash
cd frontend
npm install
npm test
```

Expected: 1 passed.

- [ ] **Step 8: Verify the production build compiles**

```bash
npm run build
```

Expected: `tsc` clean, Vite build succeeds.

- [ ] **Step 9: Commit**

```bash
cd ..
git add frontend
git commit -m "feat(00): themed frontend shell with /health connectivity via dev proxy"
```

---

### Task 10: OpenAPI → TypeScript types (`gen:api`)

**Files:**
- Create: `frontend/openapi.json` (committed contract snapshot)
- Create: `frontend/src/types/api.d.ts` (generated, committed)

- [ ] **Step 1: Dump the OpenAPI snapshot from the app (no server needed)**

```bash
cd backend
.venv/Scripts/python -c "import json; from app.main import app; open('../frontend/openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(), indent=2))"
```

- [ ] **Step 2: Generate the TS types**

```bash
cd ../frontend
npm run gen:api
```

Expected: `src/types/api.d.ts` written; open it and confirm it contains `"/predict"`, `"/market/comps"`, `"/booking"` path entries.

- [ ] **Step 3: Confirm the build still compiles with the generated file**

```bash
npm run build
```

Expected: success.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/openapi.json frontend/src/types/api.d.ts
git commit -m "feat(00): committed OpenAPI snapshot + generated TS contract types"
```

---

### Task 11: README, spec TODO resolution, full verification

**Files:**
- Create: `README.md`
- Modify: `docs/superpowers/specs/2026-07-02-assetiq-00-foundation-design.md` (mark resolved TODOs)
- Modify: `docs/superpowers/specs/2026-07-02-assetiq-overview-design.md` (mark ODX TODO resolved)

- [ ] **Step 1: Write `README.md`**

```markdown
# AssetIQ — Mercedes-Benz Resale Intelligence

Predicts a used Mercedes' resale value (RM) from a trained model, live Malaysian market
listings (Mudah.my / Carlist.my), and OBD-II/ODX vehicle data, in an interactive 3D dashboard.

Design docs: `docs/superpowers/specs/` (start with the overview).

## Prerequisites

- Python 3.11+, Node 22+
- `cp .env.example .env` (fill secrets later; everything degrades gracefully without them)

## Backend (FastAPI)

    cd backend
    python -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt   # Windows path; use .venv/bin on Unix
    cd ..
    backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload --port 8000

Run from the **repo root** so `./data/` and `.env` resolve correctly.
API docs: http://localhost:8000/docs · Contract: http://localhost:8000/openapi.json

## Frontend (React + Three.js)

    cd frontend
    npm install
    npm run dev        # http://localhost:5173 (proxies /api -> :8000)

## Tests

    cd backend && .venv/Scripts/python -m pytest      # backend unit tests
    cd frontend && npm test                            # component smoke tests

## Repo layout

    backend/app       FastAPI app: config, db, orm, schemas, routers (contract), services
    backend/ml        ingest/train/evaluate (Phase 02)
    backend/scraper   Mudah/Carlist polite scraper (Phase 01)
    frontend/         Vite + React + TS dashboard (Phase 04)
    data/sample_odx   real odxtools example PDX (consumed by Phase 03)
    docs/superpowers  specs and plans

Secrets live in `.env` (gitignored). The DB connection string is never printed or logged.
```

- [ ] **Step 2: Mark the resolved TODOs in the foundation spec**

In `docs/superpowers/specs/2026-07-02-assetiq-00-foundation-design.md`, append directly under each of these TODO lines:

- Under the `seller_type` TODO: `> **Resolved (P00 plan):** seller_type ∈ {'dealer','private','unknown'} (TEXT, default 'unknown'); posted_at is ISO-8601 YYYY-MM-DD TEXT normalised at scrape time — raw source format still confirmed at Gate 1.`
- Under the TS type-generation TODO: `> **Resolved (P00 plan):** openapi-typescript reads the committed frontend/openapi.json snapshot → src/types/api.d.ts via npm run gen:api.`
- Under the dependency-pins TODO: `> **Resolved (P00 plan):** exact pins in backend/requirements.txt and frontend/package.json; Python 3.11, Node 22.`
- Under the sample-ODX TODO: `> **Resolved (P00 plan):** data/sample_odx/somersault.pdx generated from the official mercedes-benz/odxtools somersault example, pinned to the installed odxtools version.`

In `docs/superpowers/specs/2026-07-02-assetiq-overview-design.md`, append under the cross-cutting ODX TODO: `> **Resolved (P00 plan):** committed as data/sample_odx/somersault.pdx (official odxtools example).`

- [ ] **Step 3: Full verification run**

```bash
cd backend && .venv/Scripts/python -m pytest -v && cd ..
cd frontend && npm test && npm run build && cd ..
```

Expected: every backend test green (22 tests: config 3, schemas 10, orm 2, health 2, contract 3, secret-safety 1, sample-odx 1), frontend test green, build clean.

- [ ] **Step 4: Manual end-to-end check** — run both servers, open http://localhost:5173, confirm the shell shows “API online · v0.1.0”, then stop both.

```bash
backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000 &
cd frontend && npm run dev &
# open http://localhost:5173 — expect the topbar pill: "API online · v0.1.0"
# then kill both processes
```

- [ ] **Step 5: Commit**

```bash
git add README.md docs/superpowers/specs
git commit -m "docs(00): README runbook + mark P00 TODOs resolved in specs"
```

---

## Completion

When all tasks are checked: every done-criterion in spec 00 is met (uvicorn serves `/health`; the shell calls it; all 5 tables + all schemas exist; `.env.example` committed and `.env` gitignored; `/openapi.json` carries the full contract). Use superpowers:finishing-a-development-branch to merge/PR `feat/00-foundation`, which unblocks Phases 01–05.
