"""Cleaning + feature-engineering: raw merc.csv -> training_data shape.

Mirrors 02_cleaning.ipynb. Produces data/merc_engineered.csv (raw merc.csv is
never mutated). Reproducible: REFERENCE_YEAR is fixed and noise is seeded.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import get_settings
from ml.features import add_engineered_features

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_CSV = REPO_ROOT / "data" / "merc.csv"
ENGINEERED_CSV = REPO_ROOT / "data" / "merc_engineered.csv"

REFERENCE_YEAR = 2026     # fixed for reproducibility (NOT datetime.now())
MIN_YEAR = 1990           # older listings treated as data-entry outliers
MAX_MILEAGE = 500_000     # implausibly high mileage dropped

_RENAME = {
    "price": "price_gbp",
    "fuelType": "fuel_type",
    "engineSize": "engine_size",
}
_ESSENTIAL = ["model", "year", "price_gbp", "transmission", "mileage", "fuel_type",
              "engine_size", "tax", "mpg"]


def load_raw(path: Path = RAW_CSV) -> pd.DataFrame:
    """Read the raw CSV exactly as committed."""
    return pd.read_csv(path)


def clean(df: pd.DataFrame, fx_rate: float) -> pd.DataFrame:
    """Normalise columns, drop dupes/nulls/outliers, add `age` and `price_rm`."""
    out = df.rename(columns=_RENAME).copy()
    out["model"] = out["model"].str.strip()

    out = out.dropna(subset=_ESSENTIAL)
    out = out.drop_duplicates()

    out = out[(out["year"] >= MIN_YEAR) & (out["year"] <= REFERENCE_YEAR)]
    out = out[(out["price_gbp"] > 0)]
    out = out[(out["mileage"] >= 0) & (out["mileage"] <= MAX_MILEAGE)]

    out["age"] = REFERENCE_YEAR - out["year"]
    out["price_rm"] = (out["price_gbp"] * fx_rate).round().astype(int)
    out = out.drop(columns=["price_gbp"])
    return out.reset_index(drop=True)


def clean_and_engineer(df: pd.DataFrame, fx_rate: float, seed: int = 42) -> pd.DataFrame:
    """Clean, then synthesise the simulated OBD-II features."""
    return add_engineered_features(clean(df, fx_rate), seed=seed)


def build_engineered_csv(
    df: pd.DataFrame | None = None,
    fx_rate: float | None = None,
    seed: int = 42,
    dst: Path = ENGINEERED_CSV,
) -> pd.DataFrame:
    """Build (and write) the cleaned+engineered dataset; returns the frame."""
    if fx_rate is None:
        fx_rate = get_settings().fx_gbp_to_rm
    if df is None:
        df = load_raw()
    engineered = clean_and_engineer(df, fx_rate=fx_rate, seed=seed)
    dst.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(dst, index=False)
    return engineered
