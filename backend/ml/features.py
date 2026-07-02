"""Simulated OBD-II telemetry features (spec 02, "Feature engineering").

Two columns are synthesised deterministically from existing vehicle attributes,
demonstrating how live vehicle-health signals would feed the resale valuation.
They are NOT real sensor readings. Base functions are pure; seeded Gaussian
noise is added only when building the training dataset column.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

HYBRID_FUEL = "Hybrid"
MANUAL_TRANSMISSION = "Manual"

SOH_FLOOR = 30.0          # SoH never drops below this / above 100
SOH_NOISE_STD = 2.0       # owner-care variance (percentage points)
OFFSET_NOISE_STD = 0.005  # owner-care variance on the adaptation offset
OFFSET_MAX = -1e-4        # non-manual offsets clipped strictly below zero
FEATURE_SEED = 42


def battery_soh_base(fuel_type: str, age: float, mileage: float) -> float:
    """Deterministic (unclipped) Starter Battery State-of-Health, in percent.

    Petrol/Diesel/Other: a 12V starter battery degrades mainly with TIME (age),
    modelled as exponential decay in age plus a small mileage term.
    Hybrid: the HV battery degrades mainly with CHARGE CYCLES (mileage), and does
    so NON-LINEARLY (a super-linear mileage exponent), so high-mileage hybrids
    fall off faster than a linear model predicts.
    Callers MUST clip the result (np.clip / _clip_soh) before exposing it.
    """
    if fuel_type == HYBRID_FUEL:
        cycles = mileage / 100_000.0
        return 100.0 * math.exp(-0.35 * cycles ** 1.6) - 0.4 * age
    return 100.0 * math.exp(-0.045 * age) - 0.8 * (mileage / 100_000.0)


def _clip_soh(value: float) -> float:
    return min(100.0, max(SOH_FLOOR, value))


def _clip_offset(value: float) -> float:
    """Non-manual offsets stay strictly negative (0.0 is the Manual sentinel)."""
    return min(value, OFFSET_MAX)


def trans_adapt_offset_base(transmission: str, mileage: float) -> float:
    """Deterministic Transmission Adaptation Offset (a depreciation modifier <= 0).

    Manual -> exactly 0.0 (no electronic TCU adaptation to track). For any other
    transmission (the "not manual -> automatic logic" path) the electronic TCU's
    hydraulic-adaptation wear scales with mileage, bucketed into normal /
    noticeable / critical wear bands, always strictly negative.
    Matching is case-sensitive; unrecognized/NaN transmission values take the automatic-wear path.
    """
    if transmission == MANUAL_TRANSMISSION:
        return 0.0
    if mileage < 60_000:        # normal wear
        base = -0.02
    elif mileage < 120_000:     # noticeable wear
        base = -0.05
    else:                       # critical wear
        base = -0.10
    continuous = -0.02 * (mileage / 120_000.0)   # within-band scaling, normalised to the critical-band threshold
    return base + continuous


def add_engineered_features(df: pd.DataFrame, seed: int = FEATURE_SEED) -> pd.DataFrame:
    """Return a copy of df with `battery_soh` and `trans_adapt_offset` columns.

    Requires columns: fuel_type, transmission, age, mileage. Adds seeded Gaussian
    noise; Manual rows keep an exact 0.0 offset and non-manual offsets stay < 0.
    """
    rng = np.random.default_rng(seed)
    out = df.copy()

    soh = np.array(
        [battery_soh_base(f, a, m) for f, a, m in zip(out["fuel_type"], out["age"], out["mileage"])]
    )
    soh = np.clip(soh + rng.normal(0.0, SOH_NOISE_STD, len(out)), SOH_FLOOR, 100.0)

    offset = np.array(
        [trans_adapt_offset_base(t, m) for t, m in zip(out["transmission"], out["mileage"])]
    )
    is_manual = (out["transmission"] == MANUAL_TRANSMISSION).to_numpy()
    noisy = np.minimum(offset + rng.normal(0.0, OFFSET_NOISE_STD, len(out)), OFFSET_MAX)  # array form of _clip_offset
    offset = np.where(is_manual, 0.0, noisy)

    out["battery_soh"] = np.round(soh, 2)
    out["trans_adapt_offset"] = np.round(offset, 4)
    return out


def engineer_profile(profile: dict) -> dict:
    """Noise-free engineered features for a single prediction profile.

    Requires keys: fuel_type, transmission, age, mileage. Returns a new dict with
    `battery_soh` and `trans_adapt_offset` added (deterministic, stable).
    """
    soh = _clip_soh(battery_soh_base(profile["fuel_type"], profile["age"], profile["mileage"]))
    offset = trans_adapt_offset_base(profile["transmission"], profile["mileage"])
    if profile["transmission"] != MANUAL_TRANSMISSION:
        offset = _clip_offset(offset)
    return {**profile, "battery_soh": round(soh, 2), "trans_adapt_offset": round(offset, 4)}
