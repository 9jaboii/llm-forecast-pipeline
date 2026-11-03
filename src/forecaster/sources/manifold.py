from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from forecaster.sources.http import get_json

BASE_URL = "https://api.manifold.markets/v0"


@dataclass
class MarketQuestion:
    id: str
    title: str
    url: str
    close_time: datetime | None
    market_prob: float | None
    unique_bettor_count: int


def _close_time_from_ms(ms: float | None) -> datetime | None:
    """Naive UTC, matching this project's DB/comparison convention (see
    forecaster.timeutil.utcnow) — SQLite doesn't round-trip tzinfo."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).replace(tzinfo=None)


def fetch_open_questions(limit: int, min_bettors: int) -> list[MarketQuestion]:
    # /v0/markets returns newest-created first, and most brand-new markets
    # have uniqueBettorCount 0 — a shallow overfetch (e.g. limit * 4) can
    # come back nearly empty once FC_MIN_BETTORS filters it. Pull the API's
    # max page size regardless of `limit` so there's always a real pool of
    # active markets to filter from.
    raw = get_json(f"{BASE_URL}/markets", params={"limit": 1000})
    questions: list[MarketQuestion] = []
    for market in raw:
        if market.get("outcomeType") != "BINARY":
            continue
        if market.get("isResolved"):
            continue
        bettors = market.get("uniqueBettorCount", 0)
        if bettors < min_bettors:
            continue
        questions.append(
            MarketQuestion(
                id=f"manifold:{market['id']}",
                title=market["question"],
                url=market["url"],
                close_time=_close_time_from_ms(market.get("closeTime")),
                market_prob=market.get("probability"),
                unique_bettor_count=bettors,
            )
        )
        if len(questions) >= limit:
            break
    return questions


@dataclass
class Resolution:
    is_resolved: bool
    resolution: str | None  # "YES" | "NO" | "MKT" | "CANCEL"
    resolution_time: datetime | None


def fetch_resolution(manifold_id: str) -> Resolution:
    raw = get_json(f"{BASE_URL}/market/{manifold_id}")
    return Resolution(
        is_resolved=bool(raw.get("isResolved")),
        resolution=raw.get("resolution"),
        resolution_time=_close_time_from_ms(raw.get("resolutionTime")),
    )


def resolution_to_outcome(resolution: str) -> float | None:
    if resolution == "YES":
        return 1.0
    if resolution == "NO":
        return 0.0
    return None  # MKT (partial) and CANCEL carry no clean binary outcome
