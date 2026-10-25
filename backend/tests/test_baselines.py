"""Unit tests for the baseline-comparison helpers (no network, no pipeline)."""
from scripts.baselines import _metrics, _prf


def test_metrics_mae_rmse_bias():
    m = _metrics([70.0, 60.0, 80.0], [64.0, 74.0, 58.0])
    assert m["mae"] == 14.0
    assert m["bias"] == 4.67
    assert m["max_abs_error"] == 22.0
    assert m["rmse"] == round((((6) ** 2 + (-14) ** 2 + (22) ** 2) / 3) ** 0.5, 2)


def test_prf_perfect_and_empty():
    perfect = _prf(6, 0, 0)
    assert perfect["precision"] == perfect["recall"] == perfect["f1"] == 1.0
    empty = _prf(0, 0, 6)
    assert empty["precision"] == empty["recall"] == empty["f1"] == 0.0


def test_prf_partial():
    m = _prf(6, 12, 0)
    assert m["precision"] == 0.333
    assert m["recall"] == 1.0
    assert m["f1"] == 0.5
