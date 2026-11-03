from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class ArticleLike:
    title: str
    published_at: datetime
    url: str
    domain: str


def select_articles(
    articles: list[ArticleLike],
    question_title: str,
    asof: datetime,
    max_articles: int = 8,
) -> list[ArticleLike]:
    """Leakage guard: only articles published strictly before `asof` are ever
    eligible, regardless of relevance ranking. Ranks the remainder by TF-IDF
    cosine similarity to the question title."""
    eligible = [a for a in articles if a.published_at < asof]
    if not eligible:
        return []
    if len(eligible) <= max_articles:
        return sorted(eligible, key=lambda a: a.published_at, reverse=True)

    corpus = [question_title] + [a.title for a in eligible]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    ranked = sorted(zip(sims, eligible, strict=True), key=lambda pair: pair[0], reverse=True)
    return [article for _, article in ranked[:max_articles]]


_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "in",
    "on",
    "for",
    "to",
    "and",
    "or",
    "is",
    "will",
    "be",
    "by",
    "at",
    "with",
    "this",
    "that",
    "it",
    "has",
    "have",
    "do",
    "does",
}


def extract_keywords(question_title: str, max_keywords: int = 5) -> list[str]:
    words = [w.strip(".,?!\"'()").lower() for w in question_title.split()]
    candidates = [w for w in words if w and w not in _STOPWORDS and len(w) > 2]
    seen: list[str] = []
    for w in candidates:
        if w not in seen:
            seen.append(w)
    return seen[:max_keywords] or candidates[:max_keywords]
