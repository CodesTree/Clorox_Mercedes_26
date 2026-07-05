"""Regression metrics. MAPE is guarded against near-zero target prices via a
floor (spec 02 TODO(P02)) so a cheap listing can't explode the percentage.
"""
from __future__ import annotations

import numpy as np

MAPE_FLOOR_RM = 5000.0   # rows with price_rm below this are excluded from MAPE only


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def mape(y_true: np.ndarray, y_pred: np.ndarray, floor: float = MAPE_FLOOR_RM) -> float:
    """Mean absolute percentage error (%), excluding rows below `floor`."""
    mask = y_true >= floor
    if not np.any(mask):
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def evaluate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "mae": mae(y_true, y_pred),
        "mape": mape(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "r2": r2(y_true, y_pred),
    }
