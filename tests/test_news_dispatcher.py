from datetime import UTC, datetime

import pytest

from forecaster.config import Settings
from forecaster.sources import gdelt, news, newsapi


def test_dispatches_to_gdelt_by_default(monkeypatch):
    monkeypatch.setattr(gdelt, "fetch_headlines", lambda *a, **k: ["gdelt-sentinel"])
    settings = Settings(NEWS_PROVIDER="gdelt")
    result = news.fetch_headlines(
        settings, ["x"], datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), 8
    )
    assert result == ["gdelt-sentinel"]


def test_dispatches_to_newsapi_with_key(monkeypatch):
    captured = {}

    def _fake_fetch(keywords, start, end, max_articles, api_key=None):
        captured["api_key"] = api_key
        return ["newsapi-sentinel"]

    monkeypatch.setattr(newsapi, "fetch_headlines", _fake_fetch)
    settings = Settings(NEWS_PROVIDER="newsapi", NEWSAPI_KEY="shh")
    result = news.fetch_headlines(
        settings, ["x"], datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), 8
    )
    assert result == ["newsapi-sentinel"]
    assert captured["api_key"] == "shh"


def test_unknown_provider_raises():
    settings = Settings(NEWS_PROVIDER="carrier-pigeon")
    with pytest.raises(ValueError, match="unknown FC_NEWS_PROVIDER"):
        news.fetch_headlines(
            settings, ["x"], datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), 8
        )
