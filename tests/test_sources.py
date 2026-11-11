from datetime import UTC, datetime

from forecaster.sources import gdelt, manifold, newsapi


def test_fetch_open_questions_filters_binary_resolved_and_min_bettors(monkeypatch):
    raw = [
        {
            "id": "a",
            "question": "Binary open, enough bettors",
            "url": "https://x/a",
            "outcomeType": "BINARY",
            "isResolved": False,
            "uniqueBettorCount": 20,
            "probability": 0.4,
            "closeTime": 1800000000000,
        },
        {
            "id": "b",
            "question": "Binary but too few bettors",
            "url": "https://x/b",
            "outcomeType": "BINARY",
            "isResolved": False,
            "uniqueBettorCount": 2,
            "probability": 0.4,
            "closeTime": None,
        },
        {
            "id": "c",
            "question": "Already resolved",
            "url": "https://x/c",
            "outcomeType": "BINARY",
            "isResolved": True,
            "uniqueBettorCount": 50,
            "probability": 1.0,
            "closeTime": None,
        },
        {
            "id": "d",
            "question": "Not binary",
            "url": "https://x/d",
            "outcomeType": "FREE_RESPONSE",
            "isResolved": False,
            "uniqueBettorCount": 50,
            "probability": None,
            "closeTime": None,
        },
    ]
    monkeypatch.setattr(manifold, "get_json", lambda *a, **k: raw)
    questions = manifold.fetch_open_questions(limit=10, min_bettors=10)
    assert len(questions) == 1
    assert questions[0].id == "manifold:a"
    assert questions[0].market_prob == 0.4


def test_fetch_resolution_maps_yes_no_and_other():
    assert manifold.resolution_to_outcome("YES") == 1.0
    assert manifold.resolution_to_outcome("NO") == 0.0
    assert manifold.resolution_to_outcome("CANCEL") is None
    assert manifold.resolution_to_outcome("MKT") is None


def test_fetch_headlines_parses_articles(monkeypatch):
    raw = {
        "articles": [
            {
                "url": "https://news.invalid/1",
                "title": "Headline one",
                "domain": "news.invalid",
                "seendate": "20260101120000",
            },
        ]
    }
    monkeypatch.setattr(gdelt, "get_json", lambda *a, **k: raw)
    articles = gdelt.fetch_headlines(
        ["kestrelia"],
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
        max_articles=8,
    )
    assert len(articles) == 1
    assert articles[0].title == "Headline one"


def test_fetch_headlines_empty_keywords_returns_empty():
    assert gdelt.fetch_headlines([], datetime(2026, 1, 1), datetime(2026, 1, 2)) == []


def test_fetch_headlines_swallows_rate_limit_errors(monkeypatch):
    def _raise(*a, **k):
        raise RuntimeError("GET failed after 3 attempts")

    monkeypatch.setattr(gdelt, "get_json", _raise)
    articles = gdelt.fetch_headlines(
        ["x"], datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
    )
    assert articles == []


def test_newsapi_fetch_headlines_parses_articles(monkeypatch):
    raw = {
        "status": "ok",
        "articles": [
            {
                "url": "https://news.invalid/1",
                "title": "Headline one",
                "source": {"id": "example", "name": "Example News"},
                "publishedAt": "2026-01-01T12:00:00Z",
            },
        ],
    }
    monkeypatch.setattr(newsapi, "get_json", lambda *a, **k: raw)
    articles = newsapi.fetch_headlines(
        ["kestrelia"],
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
        max_articles=8,
        api_key="test-key",
    )
    assert len(articles) == 1
    assert articles[0].title == "Headline one"
    assert articles[0].domain == "Example News"


def test_newsapi_fetch_headlines_empty_keywords_returns_empty():
    assert (
        newsapi.fetch_headlines([], datetime(2026, 1, 1), datetime(2026, 1, 2), api_key="test-key")
        == []
    )


def test_newsapi_fetch_headlines_missing_api_key_returns_empty():
    assert (
        newsapi.fetch_headlines(["x"], datetime(2026, 1, 1), datetime(2026, 1, 2), api_key=None)
        == []
    )


def test_newsapi_fetch_headlines_swallows_errors(monkeypatch):
    def _raise(*a, **k):
        raise RuntimeError("GET failed after 3 attempts")

    monkeypatch.setattr(newsapi, "get_json", _raise)
    articles = newsapi.fetch_headlines(
        ["x"], datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), api_key="bad"
    )
    assert articles == []


def test_newsapi_falls_back_to_url_domain_when_source_name_missing(monkeypatch):
    raw = {
        "articles": [
            {
                "url": "https://fallback.invalid/a",
                "title": "No source name",
                "source": {},
                "publishedAt": "2026-01-01T12:00:00Z",
            },
        ]
    }
    monkeypatch.setattr(newsapi, "get_json", lambda *a, **k: raw)
    articles = newsapi.fetch_headlines(
        ["x"], datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), api_key="k"
    )
    assert articles[0].domain == "fallback.invalid"
