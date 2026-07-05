"""Mock user-profile loader for the booking demo.

Sources the customer's name / nearest workshop / car model from a committed
JSON file so the Telegram proposal has sensible defaults when the request omits
them. Falls back to hard-coded defaults if the file is missing or malformed.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
USER_PROFILE_PATH = BACKEND_DIR / "data_demo" / "user_profile.json"

DEFAULT_USER_PROFILE: dict[str, str] = {
    "name": "Chan Zheng Shao",
    "nearest_workshop": "Hap Seng Star KL",
    "car_model": "Mercedes-AMG GT 63 S 4MATIC+",
    "purpose": "Certified inspection",
}


@lru_cache
def load_user_profile() -> dict[str, str]:
    merged = dict(DEFAULT_USER_PROFILE)
    try:
        with USER_PROFILE_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Falling back to default user profile: %s", exc)
        return merged

    if isinstance(data, dict):
        merged.update({k: str(v) for k, v in data.items() if isinstance(v, (str, int, float))})
    return merged
