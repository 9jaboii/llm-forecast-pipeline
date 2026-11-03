import math

from forecaster import aggregate


def test_mean_median_trimmed_mean():
    probs = [0.2, 0.4, 0.5, 0.6, 0.9]
    assert aggregate.mean(probs) == sum(probs) / len(probs)
    assert aggregate.median(probs) == 0.5
    assert 0.3 < aggregate.trimmed_mean(probs, proportion=0.4) < 0.7


def test_geometric_mean_of_odds_between_min_and_max():
    probs = [0.3, 0.7]
    result = aggregate.geometric_mean_of_odds(probs)
    assert min(probs) < result < max(probs)


def test_extremize_pushes_away_from_half():
    moderate = 0.6
    extreme = aggregate.extremize(moderate, alpha=2.0)
    assert extreme > moderate


def test_extremize_identity_at_alpha_one():
    p = 0.63
    assert math.isclose(aggregate.extremize(p, alpha=1.0), p, abs_tol=1e-6)


def test_aggregate_samples_dispatch():
    probs = [0.1, 0.2, 0.9]
    assert aggregate.aggregate_samples(probs, "median") == aggregate.median(probs)
    assert aggregate.aggregate_samples(probs, "mean") == aggregate.mean(probs)


def test_aggregate_samples_unknown_method_raises():
    import pytest

    with pytest.raises(ValueError):
        aggregate.aggregate_samples([0.5], "bogus")
