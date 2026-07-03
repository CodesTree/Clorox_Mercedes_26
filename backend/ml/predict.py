"""Predictor interface consumed by Phase 03.

predict(profile) -> {value_rm, low_rm, high_rm, confidence}
depreciation(profile, years) -> [{year, value_rm, retained_pct}, ...]

The two simulated OBD-II features are re-derived (noise-free) from the profile so
inference is stable; the depreciation curve recomputes battery_soh as age advances.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.features import engineer_profile
from ml.train import FEATURES, INTERVAL_HIGH_PCT, INTERVAL_LOW_PCT

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[0] / "artifacts" / "model.joblib"
CONFIDENCE = (INTERVAL_HIGH_PCT - INTERVAL_LOW_PCT) / 100.0


class Predictor:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        self.pipe = joblib.load(model_path)
        self.prep = self.pipe.named_steps["prep"]
        self.rf = self.pipe.named_steps["model"]

    def _row(self, profile: dict) -> pd.DataFrame:
        return pd.DataFrame([engineer_profile(profile)])[FEATURES]

    def _per_tree(self, row: pd.DataFrame) -> np.ndarray:
        Xt = self.prep.transform(row)
        return np.array([est.predict(Xt)[0] for est in self.rf.estimators_])

    def predict(self, profile: dict) -> dict:
        trees = self._per_tree(self._row(profile))
        value = float(np.mean(trees))
        low = max(0.0, float(np.percentile(trees, INTERVAL_LOW_PCT)))
        high = float(np.percentile(trees, INTERVAL_HIGH_PCT))
        # For a skewed per-tree sample the mean can fall outside the [4,96] band;
        # clamp so the low_rm <= value_rm <= high_rm contract holds by construction.
        high = max(high, value)
        low = min(low, value)
        return {
            "value_rm": int(round(value)),
            "low_rm": int(round(low)),
            "high_rm": int(round(high)),
            "confidence": CONFIDENCE,
        }

    def depreciation(self, profile: dict, years: int = 5) -> list[dict]:
        base_year = int(profile["year"])
        base_age = int(profile["age"])
        raw_values = []
        for step in range(years + 1):
            future = {**profile, "age": base_age + step}  # mileage held fixed per spec
            raw_values.append(float(np.mean(self._per_tree(self._row(future)))))
        # enforce non-increasing (RF is not monotonic in age) and floor at 0
        monotonic = np.minimum.accumulate(np.maximum(raw_values, 0.0))
        # degenerate zero-valuation base -> today=1.0, so retained_pct[0] reads 0.0 (not 1.0)
        today = monotonic[0] if monotonic[0] > 0 else 1.0
        return [
            {
                "year": base_year + step,
                "value_rm": int(round(monotonic[step])),
                "retained_pct": round(float(monotonic[step] / today), 4),
            }
            for step in range(years + 1)
        ]


@lru_cache(maxsize=1)
def _default_predictor() -> Predictor:
    return Predictor()


def predict(profile: dict) -> dict:
    return _default_predictor().predict(profile)


def depreciation(profile: dict, years: int = 5) -> list[dict]:
    return _default_predictor().depreciation(profile, years=years)
