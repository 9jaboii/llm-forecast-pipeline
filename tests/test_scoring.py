import math

from forecaster import scoring


def test_brier_score_perfect_and_worst():
    assert scoring.brier_score([1.0, 0.0], [1.0, 0.0]) == 0.0
    assert math.isclose(scoring.brier_score([0.5, 0.5], [1.0, 0.0]), 0.25)


def test_log_score_penalizes_confident_mistakes():
    confident_right = scoring.log_score([0.99], [1.0])
    confident_wrong = scoring.log_score([0.99], [0.0])
    assert confident_wrong > confident_right


def test_calibration_table_bins_and_counts():
    probs = [0.05, 0.15, 0.85, 0.95]
    outcomes = [0.0, 1.0, 1.0, 1.0]
    table = scoring.calibration_table(probs, outcomes, bins=10)
    assert len(table) == 10
    assert sum(row["count"] for row in table) == 4


def test_expected_calibration_error_zero_when_perfectly_calibrated():
    probs = [0.5] * 100
    outcomes = [1.0] * 50 + [0.0] * 50
    ece = scoring.expected_calibration_error(probs, outcomes, bins=2)
    assert ece < 0.05


def test_murphy_decomposition_reconstructs_brier():
    probs = [0.1, 0.3, 0.5, 0.7, 0.9]
    outcomes = [0.0, 0.0, 1.0, 1.0, 1.0]
    decomp = scoring.murphy_decomposition(probs, outcomes, bins=5)
    reconstructed = decomp["uncertainty"] - decomp["resolution"] + decomp["reliability"]
    assert math.isclose(reconstructed, decomp["brier"], abs_tol=1e-9)


def test_base_rate_forecaster_has_zero_resolution():
    base_rate = 0.4
    outcomes = [1.0] * 40 + [0.0] * 60
    probs = [base_rate] * 100
    decomp = scoring.murphy_decomposition(probs, outcomes, bins=5)
    assert math.isclose(decomp["resolution"], 0.0, abs_tol=1e-9)


def test_bootstrap_ci_narrows_with_more_data():
    import random

    rng = random.Random(0)
    small = [rng.random() for _ in range(20)]
    large = [rng.random() for _ in range(2000)]
    lo_s, hi_s = scoring.bootstrap_ci(small, lambda v: sum(v) / len(v), n_boot=500, seed=1)
    lo_l, hi_l = scoring.bootstrap_ci(large, lambda v: sum(v) / len(v), n_boot=500, seed=1)
    assert (hi_l - lo_l) < (hi_s - lo_s)
