"""Multi-source cleaning + spec enrichment: raw listings -> pooled training frame.

Mirrors 02_cleaning.ipynb. Pools three Mercedes price datasets (UK `merc.csv` GBP,
`germany_dataset.csv` EUR, `vehicles_craigslist.csv` USD), FX-converts each to RM,
harmonises them to one schema (adding `source_market`), enriches every row with
vehicle specs from `cars-spec-dataset.csv`, and synthesises the two simulated
OBD-II features. Raw CSVs are never mutated; the engineered frame is written to
`data/interim/merc_engineered.csv`.

Caveat: none of the sources are Malaysian listings — they are foreign price levels
expressed in RM via the FX rates. `source_market` lets the model separate them.
Reproducible: REFERENCE_YEAR is fixed and feature noise is seeded.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import get_settings
from ml.features import add_engineered_features

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
MERC_CSV = RAW_DIR / "merc.csv"
GERMANY_CSV = RAW_DIR / "germany_dataset.csv"
CRAIGSLIST_CSV = RAW_DIR / "vehicles_craigslist.csv"
SPEC_CSV = RAW_DIR / "cars-spec-dataset.csv"
ENGINEERED_CSV = REPO_ROOT / "data" / "interim" / "merc_engineered.csv"

REFERENCE_YEAR = 2026        # fixed for reproducibility (NOT datetime.now())
MIN_YEAR = 1990              # older listings treated as data-entry outliers
MAX_MILEAGE_KM = 500_000     # implausibly high mileage dropped
PRICE_RM_MIN = 3_000         # drop junk/placeholder prices
PRICE_RM_MAX = 2_000_000     # drop extreme outliers (craigslist has billions)
MILES_TO_KM = 1.60934        # merc (UK) + craigslist (US) mileage is in miles

# Enriched spec columns attached from cars-spec (numeric imputed at model time).
ENRICH_NUM = ["displacement_cc", "n_cylinders", "n_gears", "top_speed_kmh",
              "torque_nm", "accel_0_100_s", "boot_l"]
ENRICH_CAT = ["engine_config", "aspiration", "gear_type", "front_brake", "rear_brake"]

# --------------------------------------------------------------------------- #
# Shared normalizers                                                          #
# --------------------------------------------------------------------------- #
CLASS_TOKENS = ["CLA", "CLC", "CLK", "CLS", "CL", "GLA", "GLB", "GLC", "GLE", "GLS",
                "GLK", "GL", "SLK", "SLC", "SLR", "SLS", "SL", "EQ", "ML", "A", "B",
                "C", "E", "G", "M", "R", "S", "V", "X"]
CLASS_ALIAS = {"ML": "M"}    # the ML badge is the M-Class SUV


def canon_class(s) -> str | None:
    """Map any raw model string to a canonical Mercedes class token (or None)."""
    if not isinstance(s, str):
        return None
    t = s.upper()
    t = re.sub(r"MERCEDES[- ]?BENZ|BENZ|MERCEDES|AMG", " ", t)
    t = t.replace("-KLASSE", " CLASS").replace("KLASSE", " CLASS").replace("-CLASS", " CLASS")
    for c in CLASS_TOKENS:
        if re.search(rf"\b{c}\b", t) or re.search(rf"\b{c}[ -]?\d", t) or f"{c} CLASS" in t:
            return CLASS_ALIAS.get(c, c)
    return None


def norm_transmission(s) -> str:
    """Collapse each source's transmission spellings to a shared vocabulary."""
    if not isinstance(s, str):
        return "Other"
    t = s.strip().lower()
    if "manual" in t:
        return "Manual"
    if "semi" in t:
        return "Semi-Auto"
    if "auto" in t:
        return "Automatic"
    return "Other"


def norm_fuel(s) -> str:
    """Collapse fuel spellings to {Petrol, Diesel, Hybrid, Electric, Other}."""
    if not isinstance(s, str):
        return "Other"
    t = s.strip().lower()
    if "hybrid" in t:
        return "Hybrid"
    if "elect" in t:
        return "Electric"
    if "diesel" in t:
        return "Diesel"
    if t in ("petrol", "gas", "gasoline"):
        return "Petrol"
    return "Other"


def badge_liters(s) -> float:
    """Decode a 3-digit trim badge (e.g. 'E 220') to an approx displacement in L.

    A rough hint only: pre~2014 badges track displacement well; modern badges
    (e.g. 'E 350' = 2.0L) overestimate. Used ONLY to pick the nearest real spec
    variant during enrichment; the final `engine_size` is taken from the matched
    spec displacement, so an over-decoded badge self-corrects to a real value.
    """
    if not isinstance(s, str):
        return np.nan
    m = re.search(r"\b([1-6]\d0)\b", s.replace("-", " ")) or re.search(r"[a-zA-Z]([1-6]\d0)\b", s)
    if not m:
        return np.nan
    n = int(m.group(1))
    return round(n / 100.0, 1) if 100 <= n <= 700 else np.nan


# --------------------------------------------------------------------------- #
# cars-spec parsing -> Mercedes spec lookup                                   #
# --------------------------------------------------------------------------- #
def _first_num(s, pat=r"(\d+(?:\.\d+)?)") -> float:
    if not isinstance(s, str):
        return np.nan
    m = re.search(pat, s)
    return float(m.group(1)) if m else np.nan


def _parse_kmh(s) -> float:            # "140 mph (225 km/h)" -> 225
    return _first_num(s, r"\((\d+)\s*km/h\)")


def _parse_litres(s) -> float:         # "6.5 cuFT (184 L)" -> 184
    return _first_num(s, r"\((\d+)\s*L\)")


def _parse_gears(s) -> float:          # "9-speed automatic" -> 9
    return _first_num(s, r"(\d+)[- ]?[Ss]peed")


def _gear_type(s) -> str:
    if not isinstance(s, str):
        return "Unknown"
    t = s.lower()
    if "manual" in t and "auto" not in t:
        return "manual"
    if "dct" in t or "dual" in t:
        return "dct"
    if "auto" in t:
        return "automatic"
    return "Unknown"


def _aspiration(s) -> str:
    if not isinstance(s, str):
        return "Unknown"
    t = s.lower()
    if "turbo" in t:
        return "turbo"
    if "supercharg" in t or "compressor" in t:
        return "supercharged"
    if "electric" in t:
        return "electric"
    return "naturally_aspirated"


def _brake_cat(s) -> str:
    if not isinstance(s, str):
        return "Unknown"
    t = s.lower()
    if re.search(r"\d+/\d+\s*r\d+", t):    # tire-size garbage in the brake column
        return "Unknown"
    if "ceramic" in t:
        return "Ceramic"
    if "drum" in t:
        return "Drums"
    if "vent" in t and "disc" in t:
        return "Ventilated Discs"
    if "disc" in t:
        return "Discs"
    return "Unknown"


def _parse_years(s) -> tuple[float, float]:   # "2015, 2016, 2017" -> (2015, 2017)
    if not isinstance(s, str):
        return (np.nan, np.nan)
    yrs = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", s)]
    return (min(yrs), max(yrs)) if yrs else (np.nan, np.nan)


def load_spec(path: Path = SPEC_CSV) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def clean_spec(spec: pd.DataFrame | None = None) -> pd.DataFrame:
    """Filter cars-spec to Mercedes and parse it into a tidy variant lookup."""
    if spec is None:
        spec = load_spec()
    m = spec[spec["Company"].astype(str).str.lower().str.contains("mercedes")].copy()
    out = pd.DataFrame()
    out["variant"] = m["Model"].astype(str).str.strip()
    out["model_class"] = m["Serie"].map(canon_class)
    yr = m["Production years"].map(_parse_years)
    out["year_min"] = [a for a, _ in yr]
    out["year_max"] = [b for _, b in yr]
    out["displacement_cc"] = m["Displacement"].map(lambda s: _first_num(s, r"(\d+)\s*cm3"))
    out["n_cylinders"] = m["Cylinders"].map(lambda s: _first_num(s, r"(\d+)"))
    out["engine_config"] = m["Cylinders"].astype(str).str.upper().str.strip().where(
        m["Cylinders"].notna(), "Unknown")
    out["n_gears"] = m["Gearbox"].map(_parse_gears)
    out["gear_type"] = m["Gearbox"].map(_gear_type)
    out["aspiration"] = m["Fuel System"].map(_aspiration)
    out["top_speed_kmh"] = m["Top Speed"].map(_parse_kmh)
    out["torque_nm"] = m["Torque(Nm)"].map(lambda s: _first_num(s, r"(\d+)\s*Nm"))
    out["accel_0_100_s"] = m["Acceleration 0-62 Mph (0-100 kph)"].map(
        lambda s: _first_num(s, r"(\d+(?:\.\d+)?)\s*s"))
    out["boot_l"] = m["Cargo Volume"].map(_parse_litres)
    out["front_brake"] = m["Front brake"].map(_brake_cat)
    out["rear_brake"] = m["Rear brake"].map(_brake_cat)
    out["displacement_l"] = out["displacement_cc"] / 1000.0
    out = out.dropna(subset=["model_class", "year_min"])
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Price-dataset harmonizers -> common schema                                  #
# --------------------------------------------------------------------------- #
_HARMONIZED = ["model_class", "year", "mileage", "transmission", "fuel_type",
               "engine_size", "engine_hint", "price_rm", "source_market"]


def harmonize_merc(df: pd.DataFrame | None = None, fx: float | None = None) -> pd.DataFrame:
    if df is None:
        df = pd.read_csv(MERC_CSV)
    if fx is None:
        fx = get_settings().fx_gbp_to_rm
    out = pd.DataFrame()
    out["model_class"] = df["model"].astype(str).str.strip().map(canon_class)
    out["year"] = pd.to_numeric(df["year"], errors="coerce")
    out["mileage"] = pd.to_numeric(df["mileage"], errors="coerce") * MILES_TO_KM
    out["transmission"] = df["transmission"].map(norm_transmission)
    out["fuel_type"] = df["fuelType"].map(norm_fuel)
    out["engine_size"] = pd.to_numeric(df["engineSize"], errors="coerce")
    out["engine_hint"] = out["engine_size"]         # UK has real engine size
    out["price_rm"] = pd.to_numeric(df["price"], errors="coerce") * fx
    out["source_market"] = "uk"
    return out


def harmonize_germany(df: pd.DataFrame | None = None, fx: float | None = None) -> pd.DataFrame:
    if df is None:
        df = pd.read_csv(GERMANY_CSV)
    if fx is None:
        fx = get_settings().fx_eur_to_rm
    df = df[df["brand"].astype(str).str.lower().str.contains("mercedes")].copy()
    out = pd.DataFrame()
    out["model_class"] = df["model"].map(canon_class)
    out["year"] = pd.to_numeric(df["year"], errors="coerce")
    out["mileage"] = pd.to_numeric(df["mileage_in_km"], errors="coerce")   # already km
    out["transmission"] = df["transmission_type"].map(norm_transmission)
    out["fuel_type"] = df["fuel_type"].map(norm_fuel)
    out["engine_size"] = np.nan                     # filled by enrichment
    out["engine_hint"] = df["model"].map(badge_liters)
    out["price_rm"] = pd.to_numeric(df["price_in_euro"], errors="coerce") * fx
    out["source_market"] = "germany"
    return out


def harmonize_craigslist(df: pd.DataFrame | None = None, fx: float | None = None) -> pd.DataFrame:
    if df is None:
        df = pd.read_csv(CRAIGSLIST_CSV, low_memory=False)
    if fx is None:
        fx = get_settings().fx_usd_to_rm
    df = df[df["manufacturer"].astype(str).str.lower().str.contains("mercedes")].copy()
    out = pd.DataFrame()
    out["model_class"] = df["model"].map(canon_class)
    out["year"] = pd.to_numeric(df["year"], errors="coerce")
    out["mileage"] = pd.to_numeric(df["odometer"], errors="coerce") * MILES_TO_KM
    out["transmission"] = df["transmission"].map(norm_transmission)
    out["fuel_type"] = df["fuel"].map(norm_fuel)
    out["engine_size"] = np.nan
    out["engine_hint"] = df["model"].map(badge_liters)
    out["price_rm"] = pd.to_numeric(df["price"], errors="coerce") * fx
    out["source_market"] = "us"
    return out


def clean_pool(pool: pd.DataFrame) -> pd.DataFrame:
    """Drop nulls/outliers/dupes and add `age` on the concatenated frame."""
    pool = pool.dropna(subset=["model_class", "year", "mileage", "price_rm"]).copy()
    pool = pool[(pool["year"] >= MIN_YEAR) & (pool["year"] <= REFERENCE_YEAR)]
    pool = pool[(pool["mileage"] >= 0) & (pool["mileage"] <= MAX_MILEAGE_KM)]
    pool = pool[(pool["price_rm"] >= PRICE_RM_MIN) & (pool["price_rm"] <= PRICE_RM_MAX)]
    pool["age"] = REFERENCE_YEAR - pool["year"]
    pool["price_rm"] = pool["price_rm"].round().astype(int)
    pool = pool.drop_duplicates().reset_index(drop=True)
    return pool


# --------------------------------------------------------------------------- #
# Spec enrichment                                                             #
# --------------------------------------------------------------------------- #
def enrich(pool: pd.DataFrame, specs: pd.DataFrame) -> pd.DataFrame:
    """Attach specs by class x year (x nearest displacement via engine_hint).

    Keeps every row; `engine_size` is backfilled from the matched spec displacement
    where missing. `match_level` records the join quality per row.
    """
    by_class = {c: g for c, g in specs.groupby("model_class")}
    attach: dict[str, list] = {col: [] for col in ["variant", *ENRICH_NUM, *ENRICH_CAT]}
    matched = np.zeros(len(pool), dtype=bool)
    level: list[str] = []

    for i, row in enumerate(pool.itertuples(index=False)):
        cands = by_class.get(row.model_class)
        pick, lvl = None, "none"
        if cands is not None:
            yr_ok = cands[(cands["year_min"] <= row.year) & (cands["year_max"] >= row.year)]
            year_matched = len(yr_ok) > 0
            if not year_matched:
                yr_ok = cands                        # fall back to any year in the class
            if len(yr_ok):
                if not np.isnan(row.engine_hint):
                    idx = (yr_ok["displacement_l"] - row.engine_hint).abs().idxmin()
                    lvl = "displacement" if year_matched else "class_repr"
                else:
                    med = yr_ok["displacement_l"].median()
                    idx = (yr_ok["displacement_l"] - med).abs().idxmin()
                    lvl = "year_repr" if year_matched else "class_repr"
                pick = yr_ok.loc[idx]
        level.append(lvl)
        if pick is not None:
            matched[i] = True
            attach["variant"].append(pick["variant"])
            for col in (*ENRICH_NUM, *ENRICH_CAT):
                attach[col].append(pick[col])
        else:
            attach["variant"].append(None)
            for col in ENRICH_NUM:
                attach[col].append(np.nan)         # numeric specs -> median-imputed later
            for col in ENRICH_CAT:
                attach[col].append("Unknown")      # categoricals never NaN for the encoder

    out = pool.copy()
    for col, vals in attach.items():
        out[col] = vals
    need = out["engine_size"].isna() & out["displacement_cc"].notna()
    out.loc[need, "engine_size"] = out.loc[need, "displacement_cc"] / 1000.0
    out["spec_matched"] = matched
    out["match_level"] = level
    return out.drop(columns=["engine_hint"])


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #
def build_pool(fx: dict | None = None) -> pd.DataFrame:
    """Harmonise + concatenate + clean the training price datasets from disk.

    Craigslist (US) is intentionally excluded from the default training pool: its
    listings are the noisiest (validation MAPE ~49% vs UK 10% / germany 24%) and
    dragged accuracy down. `harmonize_craigslist` is kept for exploration / to
    re-add via `include_us=True` if desired.
    """
    s = get_settings()
    fx = fx or {"uk": s.fx_gbp_to_rm, "germany": s.fx_eur_to_rm, "us": s.fx_usd_to_rm}
    parts = [
        harmonize_merc(fx=fx["uk"]),
        harmonize_germany(fx=fx["germany"]),
    ]
    return clean_pool(pd.concat(parts, ignore_index=True))


def clean_and_engineer(pool: pd.DataFrame, specs: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Enrich the pooled frame with specs, then add the simulated OBD-II features."""
    return add_engineered_features(enrich(pool, specs), seed=seed)


def build_engineered_csv(
    pool: pd.DataFrame | None = None,
    specs: pd.DataFrame | None = None,
    seed: int = 42,
    dst: Path = ENGINEERED_CSV,
) -> pd.DataFrame:
    """Build (and write) the pooled, enriched, engineered training frame."""
    if pool is None:
        pool = build_pool()
    if specs is None:
        specs = clean_spec()
    engineered = clean_and_engineer(pool, specs, seed=seed)
    dst.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(dst, index=False)
    return engineered
