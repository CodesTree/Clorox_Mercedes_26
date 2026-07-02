from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.schemas import ObdSnapshotOut

RPM_RANGE = (700, 3600)
COOLANT_C_RANGE = (70.0, 105.0)
BATTERY_V_RANGE = (12.4, 14.4)


@dataclass(frozen=True)
class HealthInputs:
    mileage: int
    service_history_count: int
    service_history_total: int
    fault_count: int
    coolant_c: float
    battery_v: float


def _field(profile: Any, name: str, default: Any = None) -> Any:
    if isinstance(profile, dict):
        return profile.get(name, default)
    return getattr(profile, name, default)


def compute_health_score(inputs: HealthInputs) -> int:
    service_total = max(1, inputs.service_history_total)
    service_ratio = min(1.0, max(0.0, inputs.service_history_count / service_total))
    service_penalty = (1.0 - service_ratio) * 20
    fault_penalty = min(25, inputs.fault_count * 8)
    mileage_penalty = min(12, max(0, (inputs.mileage - 100_000) / 10_000))

    if inputs.battery_v < 12.6:
        battery_penalty = 12
    elif inputs.battery_v < 13.0:
        battery_penalty = 6
    else:
        battery_penalty = 0

    if inputs.coolant_c > 100:
        coolant_penalty = 12
    elif inputs.coolant_c > 95:
        coolant_penalty = 5
    elif inputs.coolant_c < 75:
        coolant_penalty = 4
    else:
        coolant_penalty = 0

    score = 100 - service_penalty - fault_penalty - mileage_penalty - battery_penalty - coolant_penalty
    return max(0, min(100, int(round(score))))


class ObdSimulator:
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def snapshot(self, profile: Any, fault_count: int = 0) -> ObdSnapshotOut:
        rpm = self._rng.randint(*RPM_RANGE)
        coolant_c = round(self._rng.uniform(*COOLANT_C_RANGE), 1)
        battery_v = round(self._rng.uniform(*BATTERY_V_RANGE), 2)
        mileage = int(_field(profile, "mileage", 0) or 0)
        service_history_count = int(_field(profile, "service_history_count", 0) or 0)
        service_history_total = int(
            _field(profile, "service_history_total", _field(profile, "service_history_max", 0)) or 0
        )
        health = compute_health_score(
            HealthInputs(
                mileage=mileage,
                service_history_count=service_history_count,
                service_history_total=service_history_total,
                fault_count=fault_count,
                coolant_c=coolant_c,
                battery_v=battery_v,
            )
        )
        return ObdSnapshotOut(
            rpm=rpm,
            coolant_c=coolant_c,
            battery_v=battery_v,
            health=health,
            odo_km=mileage,
            simulated=True,
            ts=datetime.now(timezone.utc),
        )
