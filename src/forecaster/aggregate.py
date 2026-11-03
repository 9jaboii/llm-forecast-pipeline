from __future__ import annotations

from collections.abc import Sequence

import numpy as np

_EPS = 1e-6


def _clip(p: np.ndarray) -> np.ndarray:
    return np.clip(p, _EPS, 1 - _EPS)


def to_logodds(p: float | np.ndarray) -> float | np.ndarray:
    p = _clip(np.asarray(p, dtype=float))
    return np.log(p / (1 - p))


def from_logodds(x: float | np.ndarray) -> float | np.ndarray:
    return 1 / (1 + np.exp(-np.asarray(x, dtype=float)))


def mean(probs: Sequence[float]) -> float:
    return float(np.mean(probs))


def median(probs: Sequence[float]) -> float:
    return float(np.median(probs))


def trimmed_mean(probs: Sequence[float], proportion: float = 0.2) -> float:
    p = np.sort(np.asarray(probs, dtype=float))
    n = len(p)
    k = int(n * proportion / 2)
    if k == 0 or n - 2 * k <= 0:
        return float(p.mean())
    return float(p[k : n - k].mean())


def geometric_mean_of_odds(probs: Sequence[float]) -> float:
    logodds = to_logodds(np.asarray(probs, dtype=float))
    return float(from_logodds(np.mean(logodds)))


def extremize(prob: float, alpha: float) -> float:
    """Multiply log-odds by alpha > 1 to undo averaging's timidity."""
    x = to_logodds(prob)
    return float(from_logodds(alpha * x))


_METHODS = {
    "mean": mean,
    "median": median,
    "trimmed_mean": trimmed_mean,
    "geometric_mean_of_odds": geometric_mean_of_odds,
}


def aggregate_samples(probs: Sequence[float], method: str = "median") -> float:
    if method not in _METHODS:
        raise ValueError(f"unknown aggregation method: {method}")
    return _METHODS[method](probs)
