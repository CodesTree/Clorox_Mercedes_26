import numpy as np
import pandas as pd

from ml import features as F


def test_fresh_low_mileage_car_scores_high_soh():
    # near-new petrol, low mileage -> SoH close to 100
    assert F.battery_soh_base("Petrol", age=1, mileage=5_000) > 90.0


def test_nonhybrid_soh_decreases_with_age():
    young = F.battery_soh_base("Diesel", age=3, mileage=40_000)
    old = F.battery_soh_base("Diesel", age=15, mileage=40_000)
    assert old < young


def test_hybrid_soh_decreases_with_mileage():
    low = F.battery_soh_base("Hybrid", age=3, mileage=30_000)
    high = F.battery_soh_base("Hybrid", age=3, mileage=150_000)
    assert high < low


def test_hybrid_soh_drop_is_nonlinear():
    # mid-mileage marginal drop exceeds the low-mileage marginal drop
    v0 = F.battery_soh_base("Hybrid", age=3, mileage=0)
    v50 = F.battery_soh_base("Hybrid", age=3, mileage=50_000)
    v100 = F.battery_soh_base("Hybrid", age=3, mileage=100_000)
    v150 = F.battery_soh_base("Hybrid", age=3, mileage=150_000)
    low_drop = v0 - v50
    mid_drop = v100 - v150
    assert mid_drop > low_drop


def test_offset_is_zero_for_manual():
    assert F.trans_adapt_offset_base("Manual", mileage=80_000) == 0.0


def test_offset_negative_and_decreasing_for_automatic():
    normal = F.trans_adapt_offset_base("Automatic", mileage=30_000)
    critical = F.trans_adapt_offset_base("Automatic", mileage=150_000)
    assert normal < 0.0
    assert critical < normal  # more negative as mileage rises


def test_offset_treats_non_manual_as_automatic_logic():
    # 'Semi-Auto' and 'Other' follow the automatic path (negative), not the manual sentinel
    assert F.trans_adapt_offset_base("Semi-Auto", mileage=80_000) < 0.0
    assert F.trans_adapt_offset_base("Other", mileage=80_000) < 0.0


def _sample_frame():
    return pd.DataFrame(
        {
            "fuel_type": ["Petrol", "Hybrid", "Diesel", "Petrol"],
            "transmission": ["Manual", "Automatic", "Semi-Auto", "Manual"],
            "age": [2, 5, 9, 12],
            "mileage": [10_000, 140_000, 90_000, 60_000],
        }
    )


def test_add_engineered_columns_present_and_bounded():
    out = F.add_engineered_features(_sample_frame(), seed=42)
    assert {"battery_soh", "trans_adapt_offset"} <= set(out.columns)
    assert out["battery_soh"].between(F.SOH_FLOOR, 100.0).all()
    assert (out["battery_soh"] > F.SOH_FLOOR).all()  # none pinned at the floor here


def test_manual_offset_exactly_zero_after_noise():
    out = F.add_engineered_features(_sample_frame(), seed=42)
    manual = out.loc[out["transmission"] == "Manual", "trans_adapt_offset"]
    assert (manual == 0.0).all()


def test_nonmanual_offset_strictly_negative_after_noise():
    out = F.add_engineered_features(_sample_frame(), seed=42)
    nonman = out.loc[out["transmission"] != "Manual", "trans_adapt_offset"]
    assert (nonman < 0.0).all()


def test_feature_engineering_is_reproducible():
    a = F.add_engineered_features(_sample_frame(), seed=42)
    b = F.add_engineered_features(_sample_frame(), seed=42)
    pd.testing.assert_frame_equal(a, b)


def test_engineer_profile_is_noise_free_and_deterministic():
    prof = {"fuel_type": "Petrol", "transmission": "Automatic", "age": 5, "mileage": 70_000}
    one = F.engineer_profile(prof)
    two = F.engineer_profile(prof)
    assert one == two
    assert one["trans_adapt_offset"] < 0.0
    assert F.SOH_FLOOR < one["battery_soh"] <= 100.0
