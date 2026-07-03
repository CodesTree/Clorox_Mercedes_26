import numpy as np
import pandas as pd

from ml import ingest


def _raw_frame():
    # mirrors data/merc.csv column names (note leading spaces in model, UK columns)
    return pd.DataFrame(
        {
            "model": [" SLK", " S Class", " SLK", " A Class"],
            "year": [2005, 2017, 2005, 1965],  # 1965 is an out-of-range outlier
            "price": [5200, 34948, 5200, 9000],
            "transmission": ["Automatic", "Automatic", "Automatic", "Manual"],
            "mileage": [63000, 27000, 63000, 40000],
            "fuelType": ["Petrol", "Hybrid", "Petrol", "Petrol"],
            "tax": [325, 20, 325, 150],
            "mpg": [32.1, 61.4, 32.1, 45.0],
            "engineSize": [1.8, 2.1, 1.8, 1.6],
        }
    )


def test_clean_renames_to_snake_case_and_adds_age_and_price_rm():
    out = ingest.clean(_raw_frame(), fx_rate=5.90)
    assert {"model", "year", "price_rm", "transmission", "mileage",
            "fuel_type", "tax", "mpg", "engine_size", "age"} <= set(out.columns)
    assert "price" not in out.columns and "fuelType" not in out.columns


def test_clean_strips_model_whitespace():
    out = ingest.clean(_raw_frame(), fx_rate=5.90)
    assert out["model"].str.startswith(" ").sum() == 0
    assert "SLK" in set(out["model"])


def test_age_uses_reference_year():
    out = ingest.clean(_raw_frame(), fx_rate=5.90)
    row = out[out["year"] == 2017].iloc[0]
    assert row["age"] == ingest.REFERENCE_YEAR - 2017


def test_price_rm_is_gbp_times_fx_rounded_int():
    out = ingest.clean(_raw_frame(), fx_rate=5.90)
    row = out[out["year"] == 2017].iloc[0]
    assert row["price_rm"] == round(34948 * 5.90)
    assert str(out["price_rm"].dtype).startswith("int")


def test_clean_drops_exact_duplicates():
    out = ingest.clean(_raw_frame(), fx_rate=5.90)
    # the duplicated 2005 SLK petrol row collapses to one
    assert (out["year"] == 2005).sum() == 1


def test_clean_drops_out_of_range_year_outliers():
    out = ingest.clean(_raw_frame(), fx_rate=5.90)
    assert (out["year"] < ingest.MIN_YEAR).sum() == 0  # 1965 removed


def test_clean_and_engineer_adds_obd_columns():
    out = ingest.clean_and_engineer(_raw_frame(), fx_rate=5.90, seed=42)
    assert {"battery_soh", "trans_adapt_offset"} <= set(out.columns)
    manual = out.loc[out["transmission"] == "Manual", "trans_adapt_offset"]
    assert (manual == 0.0).all()


def test_build_engineered_csv_writes_file(tmp_path):
    dst = tmp_path / "merc_engineered.csv"
    df = ingest.build_engineered_csv(_raw_frame(), fx_rate=5.90, seed=42, dst=dst)
    assert dst.exists()
    reloaded = pd.read_csv(dst)
    assert {"battery_soh", "trans_adapt_offset", "price_rm", "age"} <= set(reloaded.columns)
    assert len(reloaded) == len(df)


def test_clean_drops_rows_with_null_essential_numeric_features():
    frame = _raw_frame()
    frame.loc[0, "tax"] = np.nan
    frame.loc[1, "mpg"] = np.nan
    out = ingest.clean(frame, fx_rate=5.90)
    assert out["tax"].notna().all()
    assert out["mpg"].notna().all()
