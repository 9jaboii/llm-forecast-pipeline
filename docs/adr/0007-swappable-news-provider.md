# 0007 — Swappable news provider: GDELT or NewsAPI

## Status
Accepted

## Context
The guide's reference design uses GDELT DOC 2.0 for headline metadata: free,
no API key, broad multi-publisher coverage. In practice, during this
project's own development, a burst of debugging traffic appears to have
tripped a longer-duration IP-level block on GDELT's side — not the
documented "one request per 5 seconds" throttle, but a sustained 429 that
held for over a week, including on a bare request after hours of silence
(see the project's own incident notes; an email was sent to GDELT's
maintainer with no response as of this writing). GDELT also offers no
account-based auth at all — the only identity it can rate-limit or block by
is the calling IP, which means this failure mode isn't something a
well-behaved client can fully protect itself against.

## Decision
`src/forecaster/sources/news.py` is a thin dispatcher, selected by
`FC_NEWS_PROVIDER` (`gdelt` | `newsapi`), in front of two interchangeable
backends:
- `sources/gdelt.py` — unchanged, still the free/no-signup default.
- `sources/newsapi.py` — same shape (returns objects with `.url`, `.title`,
  `.domain`, `.published_at`), backed by newsapi.org, authenticated by an
  API key (`FC_NEWSAPI_KEY`) rather than by IP.

`pipeline.ingest_questions` calls the dispatcher, not either backend
directly, so neither `pipeline.py` nor anything downstream of it needs to
know which provider is active.

## Reasoning
Account-based auth is a meaningfully different reliability property than
IP-based rate limiting: a bad key fails predictably and is trivial to
rotate; a blocked IP can silently degrade an entire environment (this
laptop, a cloud sandbox, anywhere sharing that egress path) with no signal
beyond "zero articles" and no clear way to request it be lifted other than
emailing a volunteer maintainer. For a project whose core value proposition
depends on headline evidence actually arriving, depending on exactly one
IP-rate-limited, unauthenticated source was a real single point of failure,
discovered the hard way.

NewsAPI's free "Developer" plan has its own real limitation, disclosed
plainly rather than glossed over: its ToS restricts free-tier use to
development/testing, not a live production application. At this project's
actual scale (a few dozen headline requests a day), that's a reasonable
fit; anyone scaling this up seriously should budget for NewsAPI's paid
tier or revisit this decision.

## Consequences
- `FC_NEWS_PROVIDER` defaults to `gdelt` — switching to NewsAPI is one
  environment variable plus a key, not a code change.
- Both backends are expected to degrade gracefully to "no headlines found"
  (never a crash) — `pipeline.forecast` already treats empty headlines as
  valid input (base-rate-only reasoning), so a provider outage reduces
  forecast quality, not pipeline correctness.
- A third provider can be added the same way: match the `.url`/`.title`/
  `.domain`/`.published_at` shape, add a branch in `news.fetch_headlines`.
