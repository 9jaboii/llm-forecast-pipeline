import random

import numpy as np

from forecaster import calibration


def _biased_dataset(n=400, seed=0):
    rng = random.Random(seed)
    outcomes = []
    raw_probs = []
    for _ in range(n):
        true_p = rng.uniform(0.1, 0.9)
        outcome = 1.0 if rng.random() < true_p else 0.0
        # model systematically overstates confidence away from 0.5
        biased = 0.5 + (true_p - 0.5) * 1.6
        biased = min(max(biased, 0.01), 0.99)
        outcomes.append(outcome)
        raw_probs.append(biased)
    return np.array(raw_probs), np.array(outcomes)


def test_identity_calibrator_is_passthrough():
    cal = calibration.IdentityCalibrator()
    probs = np.array([0.1, 0.5, 0.9])
    assert np.allclose(cal.predict(probs), probs)


def test_choose_method_thresholds():
    assert calibration.choose_method(10) == "identity"
    assert calibration.choose_method(100) == "platt"
    assert calibration.choose_method(500) == "isotonic"


def test_platt_calibration_improves_brier():
    from forecaster import scoring

    raw_probs, outcomes = _biased_dataset()
    cal = calibration.fit(raw_probs, outcomes, method="platt")
    calibrated = cal.predict(raw_probs)

    raw_brier = scoring.brier_score(raw_probs, outcomes)
    calibrated_brier = scoring.brier_score(calibrated, outcomes)
    assert calibrated_brier < raw_brier


def test_isotonic_fit_predict_monotonic_on_training_thresholds():
    raw_probs, outcomes = _biased_dataset(n=600, seed=1)
    cal = calibration.fit(raw_probs, outcomes, method="isotonic")
    xs = np.array(sorted(cal.x_thresholds))
    ys = cal.predict(xs)
    assert np.all(np.diff(ys) >= -1e-9)


def test_temporal_split_respects_order():
    from datetime import datetime, timedelta

    base = datetime(2026, 1, 1)
    timestamps = [base + timedelta(days=i) for i in [5, 1, 3, 2, 4]]
    train_idx, test_idx = calibration.temporal_split(timestamps, train_frac=0.6)
    train_times = [timestamps[i] for i in train_idx]
    test_times = [timestamps[i] for i in test_idx]
    assert max(train_times) <= min(test_times)


def test_save_and_load_round_trip(tmp_path):
    raw_probs, outcomes = _biased_dataset()
    cal = calibration.fit(raw_probs, outcomes, method="platt")
    path = tmp_path / "calibrator.json"
    calibration.save(cal, str(path), n_train=len(outcomes))

    loaded, version = calibration.load(str(path))
    assert version["method"] == "platt"
    assert version["n_train"] == len(outcomes)
    np.testing.assert_allclose(loaded.predict(raw_probs), cal.predict(raw_probs))
