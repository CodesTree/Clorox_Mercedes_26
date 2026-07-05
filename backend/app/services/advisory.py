from __future__ import annotations

from typing import Any

from app.schemas import AdvisoryInterpretOut, RepairItemOut

ADVISORY_HORIZON_YEARS = 5

DEFAULT_REPAIR_BUNDLE = [
    RepairItemOut(name="Battery health check", cost_rm=4200),
    RepairItemOut(name="Brake wear service", cost_rm=7800),
    RepairItemOut(name="Cooling system inspection", cost_rm=6400),
]


def build_advisory_interpretation(
    profile: Any,
    predictor: Any,
    repairs: list[RepairItemOut] | None = None,
    horizon_years: int = ADVISORY_HORIZON_YEARS,
) -> AdvisoryInterpretOut:
    repair_items = repairs if repairs is not None else DEFAULT_REPAIR_BUNDLE
    total_repair_cost = sum(item.cost_rm for item in repair_items)

    prediction = predictor.predict(profile)
    depreciation = predictor.depreciation(profile, horizon_years)
    horizon_point = depreciation.points[-1]
    current_value = prediction.value_rm
    horizon_value = horizon_point.value_rm
    depreciation_loss = max(0, current_value - horizon_value)

    recommendation = "Repair and keep" if total_repair_cost < depreciation_loss else "Sell"
    summary = _fallback_summary(
        recommendation=recommendation,
        total_repair_cost=total_repair_cost,
        depreciation_loss=depreciation_loss,
        horizon_years=horizon_years,
    )

    return AdvisoryInterpretOut(
        recommendation=recommendation,
        summary=summary,
        horizon_years=horizon_years,
        current_value_rm=current_value,
        horizon_value_rm=horizon_value,
        depreciation_loss_rm=depreciation_loss,
        total_repair_cost_rm=total_repair_cost,
        repairs=repair_items,
        llm_used=False,
    )


def _fallback_summary(
    recommendation: str,
    total_repair_cost: int,
    depreciation_loss: int,
    horizon_years: int,
) -> str:
    if recommendation == "Repair and keep":
        return (
            f"Repair and keep is recommended because the estimated repair bundle of RM "
            f"{total_repair_cost:,} is lower than the projected {horizon_years}-year "
            f"depreciation loss of RM {depreciation_loss:,}."
        )

    return (
        f"Selling is recommended because the estimated repair bundle of RM "
        f"{total_repair_cost:,} is not lower than the projected {horizon_years}-year "
        f"depreciation loss of RM {depreciation_loss:,}."
    )
