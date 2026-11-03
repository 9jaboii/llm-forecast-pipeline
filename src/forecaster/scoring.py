from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np


def brier_score(probs: Sequence[float], outcomes: Sequence[float]) -> float:
    p = np.asarray(probs, dtype=float)
    o = np.asarray(outcomes, dtype=float)
    return float(np.mean((p - o) ** 2))


def log_score(probs: Sequence[float], outcomes: Sequence[float], eps: float = 1e-9) -> float:
    p = np.clip(np.asarray(probs, dtype=float), eps, 1 - eps)
    o = np.asarray(outcomes, dtype=float)
    return float(np.mean(-(o * np.log(p) + (1 - o) * np.log(1 - p))))


def calibration_table(
    probs: Sequence[float], outcomes: Sequence[float], bins: int = 10
) -> list[dict]:
    p = np.asarray(probs, dtype=float)
    o = np.asarray(outcomes, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    table = []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi) if i < bins - 1 else (p >= lo) & (p <= hi)
        count = int(mask.sum())
        table.append(
            {
                "bin_lo": float(lo),
                "bin_hi": float(hi),
                "avg_forecast": float(p[mask].mean()) if count else None,
                "observed_freq": float(o[mask].mean()) if count else None,
                "count": count,
            }
        )
    return table


def expected_calibration_error(
    probs: Sequence[float], outcomes: Sequence[float], bins: int = 10
) -> float:
    table = calibration_table(probs, outcomes, bins)
    n = sum(row["count"] for row in table)
    if n == 0:
        return 0.0
    gap = sum(
        row["count"] * abs(row["avg_forecast"] - row["observed_freq"])
        for row in table
        if row["count"]
    )
    return float(gap / n)


def murphy_decomposition(
    probs: Sequence[float], outcomes: Sequence[float], bins: int = 10
) -> dict[str, float]:
    p = np.asarray(probs, dtype=float)
    o = np.asarray(outcomes, dtype=float)
    n = len(o)
    base_rate = float(o.mean())
    uncertainty = base_rate * (1 - base_rate)

    table = calibration_table(probs, outcomes, bins)
    reliability = 0.0
    resolution = 0.0
    for row in table:
        if not row["count"]:
            continue
        weight = row["count"] / n
        reliability += weight * (row["avg_forecast"] - row["observed_freq"]) ** 2
        resolution += weight * (row["observed_freq"] - base_rate) ** 2

    brier = brier_score(p, o)
    return {
        "brier": brier,
        "reliability": float(reliability),
        "resolution": float(resolution),
        "uncertainty": float(uncertainty),
    }


def bootstrap_ci(
    values: Sequence[float],
    stat_fn: Callable[[Sequence[float]], float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int | None = None,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    v = np.asarray(values, dtype=float)
    n = len(v)
    if n == 0:
        return (math.nan, math.nan)
    stats = np.empty(n_boot)
    for i in range(n_boot):
        sample = v[rng.integers(0, n, size=n)]
        stats[i] = stat_fn(sample)
    lo = float(np.quantile(stats, alpha / 2))
    hi = float(np.quantile(stats, 1 - alpha / 2))
    return lo, hi
