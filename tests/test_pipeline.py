from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from forecaster import pipeline, trackrecord
from forecaster.config import Settings
from forecaster.db import Forecast, Question
from forecaster.llm.fake import FakeLLM
from forecaster.sources import gdelt, manifold


def _settings(tmp_path):
    return Settings(
        DATABASE_URL=f"sqlite:///{tmp_path}/test.db",
        TRACK_RECORD_DIR=str(tmp_path / "public"),
        CALIBRATOR_PATH=str(tmp_path / "calibrator.json"),
        MAX_QUESTIONS=5,
        SAMPLES=3,
        MIN_BETTORS=5,
    )


def test_ingest_forecast_publish_round_trip(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    from forecaster.db import init_db, make_session_factory

    init_db(settings)
    session_factory = make_session_factory(settings)

    now = datetime.now(UTC)
    fake_question = manifold.MarketQuestion(
        id="manifold:fict1",
        title="Will the fictional election have a runoff?",
        url="https://example.invalid/m/fict1",
        close_time=now + timedelta(days=10),
        market_prob=0.4,
        unique_bettor_count=20,
    )
    monkeypatch.setattr(manifold, "fetch_open_questions", lambda *a, **k: [fake_question])
    monkeypatch.setattr(
        gdelt,
        "fetch_headlines",
        lambda *a, **k: [
            gdelt.ArticleMeta(
                url="https://news.invalid/1",
                title="Election authority confirms tight race",
                domain="news.invalid",
                published_at=now - timedelta(days=1),
            )
        ],
    )

    q_added, a_added = pipeline.ingest_questions(session_factory, settings)
    assert q_added == 1
    assert a_added == 1

    llm = FakeLLM()
    made = pipeline.forecast(session_factory, settings, llm)
    assert made == 1

    with session_factory() as session:
        forecasts = session.scalars(select(Forecast)).all()
        assert len(forecasts) == 1
        assert len(forecasts[0].samples) == 3
        assert forecasts[0].calibrator_version == "identity"
        assert trackrecord.verify_chain(forecasts) is None

    # a second forecast run the same day must not duplicate
    made_again = pipeline.forecast(session_factory, settings, llm)
    assert made_again == 0

    pipeline.publish(session_factory, settings)
    import os

    assert os.path.exists(os.path.join(settings.TRACK_RECORD_DIR, "index.html"))
    assert os.path.exists(os.path.join(settings.TRACK_RECORD_DIR, "manifest.json"))


def test_resolve_updates_question_status(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    from forecaster.db import init_db, make_session_factory

    init_db(settings)
    session_factory = make_session_factory(settings)
    now = datetime.now(UTC)

    with session_factory() as session:
        session.add(
            Question(
                id="manifold:fict2",
                source="manifold",
                title="Will it resolve?",
                url="https://example.invalid/m/fict2",
                close_time=now,
                created_at=now,
                market_prob=0.5,
                status="open",
            )
        )
        session.commit()

    monkeypatch.setattr(
        manifold,
        "fetch_resolution",
        lambda market_id: manifold.Resolution(
            is_resolved=True, resolution="YES", resolution_time=now
        ),
    )

    resolved = pipeline.resolve(session_factory, settings)
    assert resolved == 1

    with session_factory() as session:
        q = session.get(Question, "manifold:fict2")
        assert q.status == "resolved"
        assert q.resolution == 1.0


def test_skips_question_when_model_gives_no_parseable_probability(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    from forecaster.db import init_db, make_session_factory

    init_db(settings)
    session_factory = make_session_factory(settings)
    now = datetime.now(UTC)

    with session_factory() as session:
        session.add(
            Question(
                id="manifold:fict3",
                source="manifold",
                title="Unanswerable?",
                url="https://example.invalid/m/fict3",
                close_time=now,
                created_at=now,
                market_prob=0.5,
                status="open",
            )
        )
        session.commit()

    class _MuteLLM:
        model_name = "mute-v1"

        def complete(self, system, user, temperature, max_tokens):
            return "I refuse to give a number."

    made = pipeline.forecast(session_factory, settings, _MuteLLM())
    assert made == 0
