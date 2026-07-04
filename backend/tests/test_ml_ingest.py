import numpy as np
import pandas as pd

from ml import ingest


# --------------------------------------------------------------------------- #
# Raw-shape fixtures mirroring each source's real column names                #
# --------------------------------------------------------------------------- #
def _merc_raw():
    return pd.DataFrame({
        "model": [" SLK", " S Class", " SLK", " A Class"],
        "year": [2005, 2017, 2005, 1965],          # 1965 is an out-of-range outlier
        "price": [5200, 34948, 5200, 9000],        # GBP
        "transmission": ["Automatic", "Automatic", "Automatic", "Manual"],
        "mileage": [63000, 27000, 63000, 40000],   # miles
        "fuelType": ["Petrol", "Hybrid", "Petrol", "Petrol"],
        "tax": [325, 20, 325, 150],
        "mpg": [32.1, 61.4, 32.1, 45.0],
        "engineSize": [1.8, 2.1, 1.8, 1.6],
    })


def _germany_raw():
    return pd.DataFrame({
        "brand": ["mercedes-benz", "bmw", "mercedes-benz"],
        "model": ["Mercedes-Benz E 220", "BMW 320", "Mercedes-Benz SL 500"],
        "year": [2015, 2016, 2008],
        "price_in_euro": ["25000", "20000", "40000"],
        "transmission_type": ["Automatic", "Manual", "Automatic"],
        "fuel_type": ["Diesel", "Petrol", "Petrol"],
        "mileage_in_km": [90000.0, 50000.0, 120000.0],
    })


def _spec_raw():
    return pd.DataFrame({
        "Model": ["Mercedes-Benz E 220 (W212)", "Mercedes-Benz SL 500 (R230)", "BMW 3"],
        "Serie": ["E-Klasse", "SL-Klasse", "3 Series"],
        "Company": ["Mercedes-Benz", "Mercedes-Benz", "BMW"],
        "Body style": ["Sedan", "Convertible", "Sedan"],
        "Production years": ["2013, 2014, 2015, 2016", "2006, 2007, 2008, 2009", "2012"],
        "Cylinders": ["L4", "V8", "L6"],
        "Displacement": ["2143 cm3", "5461 cm3", "2979 cm3"],
        "Power(HP)": ["170 HP @ 3000 RPM", "388 HP @ 5000 RPM", "306 HP @ 5800 RPM"],
        "Torque(Nm)": ["400 Nm @ 1400 RPM", "530 Nm @ 2800 RPM", "400 Nm @ 1200 RPM"],
        "Fuel System": ["Turbocharged Common Rail", "Multipoint Injection", "Turbocharged"],
        "Fuel": ["Diesel", "Gasoline", "Gasoline"],
        "Top Speed": ["145 mph (233 km/h)", "155 mph (250 km/h)", "155 mph (250 km/h)"],
        "Acceleration 0-62 Mph (0-100 kph)": ["8.4 s", "5.4 s", "5.1 s"],
        "Drive Type": ["Rear Wheel Drive", "Rear Wheel Drive", "Rear Wheel Drive"],
        "Gearbox": ["7-speed automatic", "7-speed automatic", "8-speed automatic"],
        "Front brake": ["Ventilated Discs", "Ventilated Discs", "Ventilated Discs"],
        "Rear brake": ["Discs", "Ventilated Discs", "Discs"],
        "Cargo Volume": ["19.2 cuFT (540 L)", "10.2 cuFT (289 L)", "17 cuFT (480 L)"],
    })


# --------------------------------------------------------------------------- #
# Normalizers                                                                 #
# --------------------------------------------------------------------------- #
def test_canon_class_maps_spellings_and_ml_alias():
    assert ingest.canon_class(" S Class") == "S"
    assert ingest.canon_class("Mercedes-Benz E 220") == "E"
    assert ingest.canon_class("E-Klasse") == "E"
    assert ingest.canon_class("ml350") == "M"           # ML badge aliases to M
    assert ingest.canon_class("200") is None            # numeric-only -> unmapped


def test_norm_transmission_and_fuel_collapse_to_shared_vocab():
    assert ingest.norm_transmission("Semi-automatic") == "Semi-Auto"
    assert ingest.norm_transmission("automatic") == "Automatic"
    assert ingest.norm_transmission("Unknown") == "Other"
    assert ingest.norm_fuel("gas") == "Petrol"
    assert ingest.norm_fuel("Diesel Hybrid") == "Hybrid"
    assert ingest.norm_fuel("06/2009") == "Other"       # germany's leaked garbage


def test_badge_liters_decodes_trim_number():
    assert ingest.badge_liters("Mercedes-Benz E 220") == 2.2
    assert ingest.badge_liters("ml350") == 3.5
    assert np.isnan(ingest.badge_liters("s-class"))


# --------------------------------------------------------------------------- #
# Harmonizers                                                                 #
# --------------------------------------------------------------------------- #
def test_harmonize_merc_converts_miles_to_km_and_price_to_rm():
    out = ingest.harmonize_merc(_merc_raw(), fx=5.90)
    assert list(out.columns) == ingest._HARMONIZED
    row = out.iloc[1]
    assert row["price_rm"] == 34948 * 5.90
    assert row["mileage"] == 27000 * ingest.MILES_TO_KM
    assert (out["source_market"] == "uk").all()
    assert out.iloc[1]["engine_hint"] == 2.1          # UK uses real engine size


def test_harmonize_germany_filters_mercedes_and_decodes_badge():
    out = ingest.harmonize_germany(_germany_raw(), fx=5.05)
    assert len(out) == 2                               # BMW row dropped
    assert (out["source_market"] == "germany").all()
    assert out["engine_size"].isna().all()             # filled later by enrichment
    assert out.iloc[0]["engine_hint"] == 2.2           # 'E 220' -> 2.2


# --------------------------------------------------------------------------- #
# Pool cleaning                                                               #
# --------------------------------------------------------------------------- #
def test_clean_pool_drops_outliers_dupes_and_adds_age():
    pool = pd.concat([ingest.harmonize_merc(_merc_raw(), fx=5.90)], ignore_index=True)
    out = ingest.clean_pool(pool)
    assert (out["year"] >= ingest.MIN_YEAR).all()      # 1965 A-Class removed
    assert (out["year"] == 2005).sum() == 1            # duplicate SLK collapsed
    assert (out["age"] == ingest.REFERENCE_YEAR - out["year"]).all()
    assert str(out["price_rm"].dtype).startswith("int")


# --------------------------------------------------------------------------- #
# Spec cleaning + enrichment                                                  #
# --------------------------------------------------------------------------- #
def test_clean_spec_parses_and_filters_mercedes():
    specs = ingest.clean_spec(_spec_raw())
    assert len(specs) == 2                             # BMW dropped
    e = specs[specs["model_class"] == "E"].iloc[0]
    assert e["displacement_cc"] == 2143
    assert e["year_min"] == 2013 and e["year_max"] == 2016
    assert e["n_gears"] == 7
    assert e["gear_type"] == "automatic"
    assert e["aspiration"] == "turbo"
    assert e["top_speed_kmh"] == 233
    assert e["boot_l"] == 540


def test_enrich_attaches_specs_backfills_engine_size_keeps_all_rows():
    specs = ingest.clean_spec(_spec_raw())
    pool = ingest.clean_pool(ingest.harmonize_germany(_germany_raw(), fx=5.05))
    out = ingest.enrich(pool, specs)
    assert len(out) == len(pool)                       # no rows dropped
    assert {"battery_soh"}.isdisjoint(out.columns)     # engineering happens later
    assert out["engine_size"].notna().all()            # backfilled from matched spec
    assert (out["match_level"] != "none").all()
    e = out[out["model_class"] == "E"].iloc[0]
    assert e["torque_nm"] == 400 and e["top_speed_kmh"] == 233


def test_clean_and_engineer_adds_obd_columns():
    specs = ingest.clean_spec(_spec_raw())
    pool = ingest.clean_pool(ingest.harmonize_germany(_germany_raw(), fx=5.05))
    out = ingest.clean_and_engineer(pool, specs, seed=42)
    assert {"battery_soh", "trans_adapt_offset"} <= set(out.columns)
    manual = out.loc[out["transmission"] == "Manual", "trans_adapt_offset"]
    assert (manual == 0.0).all()


def test_build_engineered_csv_writes_file(tmp_path):
    specs = ingest.clean_spec(_spec_raw())
    pool = ingest.clean_pool(ingest.harmonize_germany(_germany_raw(), fx=5.05))
    dst = tmp_path / "merc_engineered.csv"
    df = ingest.build_engineered_csv(pool=pool, specs=specs, seed=42, dst=dst)
    assert dst.exists()
    reloaded = pd.read_csv(dst)
    assert {"battery_soh", "trans_adapt_offset", "price_rm", "age",
            "source_market", "engine_size"} <= set(reloaded.columns)
    assert len(reloaded) == len(df)
