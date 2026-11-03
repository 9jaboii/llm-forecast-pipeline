from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from forecaster.sources.http import get_json

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT's DOC 2.0 API asks for at most one request every 5 seconds; it
# enforces this by returning a 200 with a plain-text notice rather than a
# 429, so the only reliable fix is a client-side throttle, not retries.
# In practice, from a shared/cloud sandbox IP (aggregate traffic from other
# tenants counts against the same limit), 5s was not enough — empirically
# confirmed to clear reliably around 20s. This only affects how long
# `forecaster ingest` takes, not correctness, so it's set conservatively.
_MIN_INTERVAL_SECONDS = 20.0
_last_request_at = 0.0


def _respect_rate_limit() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL_SECONDS:
        time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
    _last_request_at = time.monotonic()


@dataclass
class ArticleMeta:
    url: str
    title: str
    domain: str
    published_at: datetime


def _parse_seendate(value: str) -> datetime:
    """GDELT's seendate is UTC; kept naive to match this project's DB
    convention (see forecaster.timeutil.utcnow)."""
    return datetime.strptime(value, "%Y%m%d%H%M%S")


def fetch_headlines(
    keywords: list[str], start_date: datetime, end_date: datetime, max_articles: int = 8
) -> list[ArticleMeta]:
    if not keywords:
        return []
    query = " ".join(keywords)
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": str(max_articles),
        "format": "json",
        "startdatetime": start_date.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end_date.strftime("%Y%m%d%H%M%S"),
        "sort": "datedesc",
    }
    _respect_rate_limit()
    try:
        # Longer backoff than the default: a rate-limit response here means
        # "wait longer," not "retry fast" (see _MIN_INTERVAL_SECONDS above).
        raw = get_json(BASE_URL, params=params, retries=3, backoff_base=10.0)
    except RuntimeError:
        return []  # GDELT sometimes rate-limits or returns nothing; non-fatal

    articles = []
    for item in raw.get("articles", []):
        try:
            published_at = _parse_seendate(item["seendate"])
        except (KeyError, ValueError):
            continue
        domain = item.get("domain") or urlparse(item.get("url", "")).netloc
        articles.append(
            ArticleMeta(
                url=item.get("url", ""),
                title=item.get("title", ""),
                domain=domain,
                published_at=published_at,
            )
        )
    return articles
