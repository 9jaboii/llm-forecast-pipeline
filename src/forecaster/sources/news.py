from __future__ import annotations

from datetime import datetime

from forecaster.config import Settings
from forecaster.sources import gdelt, newsapi


def fetch_headlines(
    settings: Settings,
    keywords: list[str],
    start_date: datetime,
    end_date: datetime,
    max_articles: int,
) -> list:
    """Routes to whichever provider FC_NEWS_PROVIDER names. Both backends
    return objects with the same shape (.url, .title, .domain,
    .published_at), so callers don't need to know which one is active.
    See docs/adr/0007-swappable-news-provider.md for why this exists:
    GDELT's rate limit turned out to depend on shared/noisy IP traffic this
    project doesn't control."""
    if settings.NEWS_PROVIDER == "newsapi":
        return newsapi.fetch_headlines(
            keywords, start_date, end_date, max_articles, api_key=settings.NEWSAPI_KEY
        )
    if settings.NEWS_PROVIDER == "gdelt":
        return gdelt.fetch_headlines(keywords, start_date, end_date, max_articles)
    raise ValueError(f"unknown FC_NEWS_PROVIDER: {settings.NEWS_PROVIDER}")
