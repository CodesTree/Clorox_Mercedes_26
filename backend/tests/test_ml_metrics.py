import numpy as np

from ml import metrics


def test_mae_matches_hand_computed():
    y = np.array([100.0, 200.0, 300.0])
    p = np.array([110.0, 190.0, 330.0])
    # |10|+|10|+|30| = 50 -> /3
    assert metrics.mae(y, p) == 50.0 / 3.0


def test_rmse_matches_hand_computed():
    y = np.array([0.0, 0.0, 0.0])
    p = np.array([3.0, 4.0, 0.0])
    # sqrt((9+16+0)/3) = sqrt(25/3)
    assert metrics.rmse(y, p) == np.sqrt(25.0 / 3.0)


def test_r2_is_one_for_perfect_prediction():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert metrics.r2(y, y.copy()) == 1.0


def test_mape_matches_hand_computed_above_floor():
    y = np.array([10_000.0, 20_000.0])
    p = np.array([11_000.0, 18_000.0])
    # (0.10 + 0.10)/2 * 100 = 10.0
    assert metrics.mape(y, p) == 10.0


def test_mape_excludes_rows_below_floor():
    y = np.array([1_000.0, 20_000.0])   # 1000 is below MAPE_FLOOR_RM
    p = np.array([500.0, 22_000.0])     # the cheap row would be 50% error if counted
    # only the 20k row counts: |2000/20000| = 0.10 -> 10.0
    assert metrics.mape(y, p) == 10.0


def test_evaluate_metrics_returns_all_four():
    y = np.array([10_000.0, 20_000.0, 30_000.0])
    p = np.array([9_000.0, 21_000.0, 33_000.0])
    out = metrics.evaluate_metrics(y, p)
    assert set(out) == {"mae", "mape", "rmse", "r2"}
