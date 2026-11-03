# 0005 — Data licensing and the leakage guard

## Status
Accepted

## Context
This project touches third-party data (Manifold Markets questions, GDELT
news metadata) and must be safe to publish publicly in two separate senses:
no secrets, and no content the project doesn't have the right to
redistribute. Separately, a forecasting backtest is only meaningful if it
never sees information from after the forecast was made.

## Decision — what gets published
| Source | Fetched | Stored | Published |
|---|---|---|---|
| Manifold Markets | question text, link, close date, market probability, resolution | yes (database) | question title and link only, alongside this project's own forecasts |
| GDELT DOC 2.0 | article metadata only: URL, headline, domain, date | yes (database) | no — headlines are model input, never republished |
| Claude (Anthropic/Bedrock) | model responses | probability + rationale in the database | probability only; rationale not published by default |

Article *bodies* are never downloaded. Full news articles are copyrighted;
using a short headline privately as model input and publishing only this
project's own probabilities with a link to the original question keeps
everything published entirely original. `data/` is git-ignored so fetched
material never lands in the repository itself. Tests and the demo
(`src/forecaster/demo.py`) use entirely invented cities, companies, and
countries — the repository contains no third-party content even in its
fixtures.

## Decision — the leakage guard
`retrieval.select_articles` enforces `published_at < asof` unconditionally,
before any relevance ranking happens — there is no code path that can
select or even consider an article published after the forecast time.
`pipeline.forecast` is forward-only: it only ever forecasts currently-open
questions, never a question selected with the benefit of hindsight. See
`notebooks/05_backtest_leakage.ipynb` for a worked demonstration of how
small a leak needs to be before it makes a useless system look skilled.

## Consequences
- Swapping in a different news or market source (`docs/runbooks/` /
  `src/forecaster/sources/`) must preserve both constraints: check the new
  source's API terms before storing anything, and route it through the
  same `published_at < asof` filter before it ever reaches a prompt.
- Retrieval improvements (e.g. swapping TF-IDF for vector search, per the
  guide's §06 "swapping components" notes) must keep the `asof` filter —
  it is not optional tuning, it's the leakage guard.
