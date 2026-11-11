from __future__ import annotations

import os
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from forecaster import aggregate, calibration, forecast_prompt, trackrecord
from forecaster.config import Settings
from forecaster.db import Article, Forecast, Question
from forecaster.llm.base import LLMClient
from forecaster.retrieval import ArticleLike, extract_keywords, select_articles
from forecaster.sources import manifold, news
from forecaster.timeutil import utcnow

SYSTEM_PROMPT = (
    "You are a careful, well-calibrated probabilistic forecaster. Follow the "
    "user's instructions exactly, including the required output format."
)
MAX_TOKENS = 1024


def ingest_questions(session_factory: sessionmaker[Session], settings: Settings) -> tuple[int, int]:
    questions_added = 0
    articles_added = 0
    now = utcnow()
    lookback_start = now - timedelta(days=settings.LOOKBACK_DAYS)

    fetched = manifold.fetch_open_questions(settings.MAX_QUESTIONS, settings.MIN_BETTORS)

    with session_factory() as session:
        for q in fetched:
            existing = session.get(Question, q.id)
            if existing is None:
                session.add(
                    Question(
                        id=q.id,
                        source="manifold",
                        title=q.title,
                        url=q.url,
                        close_time=q.close_time,
                        created_at=now,
                        market_prob=q.market_prob,
                        status="open",
                    )
                )
                session.flush()
                questions_added += 1

            keywords = extract_keywords(q.title)
            headlines = news.fetch_headlines(
                settings, keywords, lookback_start, now, settings.MAX_ARTICLES
            )
            existing_urls = {
                a.url for a in session.scalars(select(Article).where(Article.question_id == q.id))
            }
            for h in headlines:
                if h.url in existing_urls:
                    continue
                session.add(
                    Article(
                        question_id=q.id,
                        url=h.url,
                        title=h.title,
                        domain=h.domain,
                        published_at=h.published_at,
                        fetched_at=now,
                    )
                )
                articles_added += 1
        session.commit()

    return questions_added, articles_added


def _load_calibrator(settings: Settings):
    if os.path.exists(settings.CALIBRATOR_PATH):
        cal, version = calibration.load(settings.CALIBRATOR_PATH)
        version_str = f"{version['method']}-{version['date'][:10]}-n{version['n_train']}"
        return cal, version_str
    cal = calibration.IdentityCalibrator()
    return cal, "identity"


def forecast(
    session_factory: sessionmaker[Session], settings: Settings, llm_client: LLMClient
) -> int:
    now = utcnow()
    today = now.date()
    made = 0
    calibrator, calibrator_version = _load_calibrator(settings)
    prompt_sha = forecast_prompt.prompt_sha256()

    with session_factory() as session:
        open_questions = session.scalars(select(Question).where(Question.status == "open")).all()
        last_forecast = session.scalars(
            select(Forecast).order_by(Forecast.id.desc()).limit(1)
        ).first()
        prev_hash = last_forecast.hash if last_forecast else trackrecord.GENESIS_HASH

        for q in open_questions:
            already_today = session.scalars(
                select(Forecast).where(
                    Forecast.question_id == q.id,
                    Forecast.created_at >= datetime(today.year, today.month, today.day),
                )
            ).first()
            if already_today:
                continue

            articles = session.scalars(select(Article).where(Article.question_id == q.id)).all()
            article_likes = [
                ArticleLike(title=a.title, published_at=a.published_at, url=a.url, domain=a.domain)
                for a in articles
            ]
            selected = select_articles(article_likes, q.title, now, settings.MAX_ARTICLES)
            headlines = [a.title for a in selected]
            prompt = forecast_prompt.build_prompt(q.title, q.close_time, now, headlines)

            samples: list[float] = []
            for _ in range(settings.SAMPLES):
                completion = llm_client.complete(
                    system=SYSTEM_PROMPT,
                    user=prompt,
                    temperature=settings.TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                )
                prob = forecast_prompt.parse_probability(completion)
                if prob is not None:
                    samples.append(prob)

            if not samples:
                continue  # "No parseable probability" — question skipped safely

            raw_prob = aggregate.aggregate_samples(samples, method="median")
            calibrated_prob = float(calibrator.predict([raw_prob])[0])

            fields = {
                "question_id": q.id,
                "created_at": now.isoformat(),
                "model": llm_client.model_name,
                "prompt_version": forecast_prompt.PROMPT_VERSION,
                "prompt_sha256": prompt_sha,
                "raw_prob": raw_prob,
                "calibrated_prob": calibrated_prob,
                "calibrator_version": calibrator_version,
            }
            new_hash = trackrecord.compute_hash(prev_hash, fields)

            session.add(
                Forecast(
                    question_id=q.id,
                    created_at=now,
                    model=llm_client.model_name,
                    prompt_version=forecast_prompt.PROMPT_VERSION,
                    prompt_sha256=prompt_sha,
                    samples=samples,
                    raw_prob=raw_prob,
                    calibrated_prob=calibrated_prob,
                    calibrator_version=calibrator_version,
                    prev_hash=prev_hash,
                    hash=new_hash,
                )
            )
            prev_hash = new_hash
            made += 1
        session.commit()

    return made


def resolve(session_factory: sessionmaker[Session], settings: Settings) -> int:
    resolved_count = 0
    with session_factory() as session:
        open_questions = session.scalars(select(Question).where(Question.status == "open")).all()
        for q in open_questions:
            manifold_id = q.id.removeprefix("manifold:")
            try:
                res = manifold.fetch_resolution(manifold_id)
            except RuntimeError:
                continue
            if not res.is_resolved:
                continue
            outcome = manifold.resolution_to_outcome(res.resolution or "")
            if outcome is None:
                continue  # MKT / CANCEL: no clean binary outcome
            q.status = "resolved"
            q.resolution = outcome
            q.resolved_at = res.resolution_time or utcnow()
            resolved_count += 1
        session.commit()
    return resolved_count


def publish(session_factory: sessionmaker[Session], settings: Settings) -> None:
    with session_factory() as session:
        questions = session.scalars(select(Question)).all()
        forecasts_by_question: dict[str, list[Forecast]] = {}
        for q in questions:
            rows = session.scalars(
                select(Forecast).where(Forecast.question_id == q.id).order_by(Forecast.created_at)
            ).all()
            if rows:
                forecasts_by_question[q.id] = list(rows)

    trackrecord.build_site(settings.TRACK_RECORD_DIR, questions, forecasts_by_question)

    if settings.TRACK_RECORD_BUCKET:
        _upload_snapshot(settings)


def _upload_snapshot(settings: Settings) -> None:
    import boto3

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    stamp = utcnow().strftime("%Y/%m/%d/%H%M%S")
    local_dir = settings.TRACK_RECORD_DIR
    for name in ("index.html", "track-record.json", "manifest.json"):
        path = os.path.join(local_dir, name)
        if not os.path.exists(path):
            continue
        key = f"snapshots/{stamp}/{name}"
        s3.upload_file(path, settings.TRACK_RECORD_BUCKET, key)


def calibrate(
    session_factory: sessionmaker[Session], settings: Settings, method: str = "auto"
) -> int:
    import numpy as np

    with session_factory() as session:
        rows = session.scalars(
            select(Forecast)
            .join(Question, Forecast.question_id == Question.id)
            .where(Question.status == "resolved", Question.resolution.is_not(None))
        ).all()
        pairs = [(row.created_at, row.raw_prob, row.question.resolution) for row in rows]
    if not pairs:
        return 0

    timestamps = [p[0] for p in pairs]
    raw_probs = np.array([p[1] for p in pairs])
    outcomes = np.array([p[2] for p in pairs])

    train_idx, _ = calibration.temporal_split(timestamps)
    calibrator = calibration.fit(raw_probs[train_idx], outcomes[train_idx], method=method)
    calibration.save(calibrator, settings.CALIBRATOR_PATH, n_train=len(train_idx))
    return len(train_idx)


def daily(
    session_factory: sessionmaker[Session], settings: Settings, llm_client: LLMClient
) -> dict:
    resolved_count = resolve(session_factory, settings)
    questions_added, articles_added = ingest_questions(session_factory, settings)
    forecasts_made = forecast(session_factory, settings, llm_client)
    publish(session_factory, settings)
    return {
        "resolved": resolved_count,
        "questions_added": questions_added,
        "articles_added": articles_added,
        "forecasts_made": forecasts_made,
    }
