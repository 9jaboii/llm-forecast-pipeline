from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from forecaster.sources.http import get_json

BASE_URL = "https://newsapi.org/v2/everything"


@dataclass
class ArticleMeta:
    url: str
    title: str
    domain: str
    published_at: datetime


def _parse_published_at(value: str) -> datetime:
    """NewsAPI returns UTC ISO-8601 with a 'Z' suffix; kept naive to match
    this project's DB convention (see forecaster.timeutil.utcnow)."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def fetch_headlines(
    keywords: list[str],
    start_date: datetime,
    end_date: datetime,
    max_articles: int = 8,
    api_key: str | None = None,
) -> list[ArticleMeta]:
    if not keywords or not api_key:
        return []
    params = {
        "q": " ".join(keywords),
        "from": start_date.date().isoformat(),
        "to": end_date.date().isoformat(),
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": str(min(max_articles, 100)),
    }
    try:
        raw = get_json(BASE_URL, params=params, headers={"X-Api-Key": api_key})
    except RuntimeError:
        return []  # bad key, over quota, or no coverage — non-fatal, same as gdelt.py

    articles = []
    for item in raw.get("articles", [])[:max_articles]:
        published_raw = item.get("publishedAt")
        if not published_raw:
            continue
        try:
            published_at = _parse_published_at(published_raw)
        except ValueError:
            continue
        url = item.get("url", "")
        source = item.get("source") or {}
        domain = source.get("name") or urlparse(url).netloc
        articles.append(
            ArticleMeta(
                url=url,
                title=item.get("title") or "",
                domain=domain,
                published_at=published_at,
            )
        )
    return articles
