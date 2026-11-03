from datetime import UTC, datetime, timedelta

from forecaster.retrieval import ArticleLike, extract_keywords, select_articles


def _article(title, days_before_asof, asof):
    return ArticleLike(
        title=title,
        published_at=asof - timedelta(days=days_before_asof),
        url=f"https://example.invalid/{title}",
        domain="example.invalid",
    )


def test_select_articles_excludes_future_published_at():
    asof = datetime(2026, 6, 1, tzinfo=UTC)
    future = ArticleLike(
        title="leaked future headline",
        published_at=asof + timedelta(days=1),
        url="https://example.invalid/future",
        domain="example.invalid",
    )
    past = _article("past headline about the election", 2, asof)
    selected = select_articles([future, past], "the election", asof, max_articles=8)
    titles = {a.title for a in selected}
    assert "leaked future headline" not in titles
    assert "past headline about the election" in titles


def test_select_articles_ranks_by_relevance_when_over_limit():
    asof = datetime(2026, 6, 1, tzinfo=UTC)
    relevant = _article("Kestrelia central bank raises interest rates", 1, asof)
    irrelevant = [_article(f"unrelated sports result number {i}", 1, asof) for i in range(10)]
    selected = select_articles(
        [relevant, *irrelevant],
        "Kestrelia central bank interest rate decision",
        asof,
        max_articles=3,
    )
    assert relevant.title in {a.title for a in selected}
    assert len(selected) == 3


def test_select_articles_empty_when_nothing_eligible():
    asof = datetime(2026, 6, 1, tzinfo=UTC)
    future = ArticleLike(
        title="too new",
        published_at=asof + timedelta(hours=1),
        url="https://example.invalid/x",
        domain="example.invalid",
    )
    assert select_articles([future], "anything", asof) == []


def test_extract_keywords_drops_stopwords_and_dedupes():
    keywords = extract_keywords("Will the the market close before the close date?")
    assert "the" not in keywords
    assert len(keywords) == len(set(keywords))
    assert len(keywords) <= 5
