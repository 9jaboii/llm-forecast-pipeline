from sqlalchemy import select

from forecaster import demo, pipeline, scoring
from forecaster.config import Settings
from forecaster.db import Forecast, Question, init_db, make_session_factory
from forecaster.llm.fake import FakeLLM


def test_demo_generates_only_fictional_content(tmp_path):
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path}/demo.db")
    init_db(settings)
    session_factory = make_session_factory(settings)

    demo.generate_demo_data(session_factory, n_questions=20)

    with session_factory() as session:
        questions = session.scalars(select(Question)).all()
        assert len(questions) == 20
        for q in questions:
            assert q.url.endswith(".invalid/questions/" + q.id.split(":")[1])
            assert q.status == "open"


def test_demo_end_to_end_brier_near_no_skill_baseline(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path}/demo.db",
        TRACK_RECORD_DIR=str(tmp_path / "public"),
        CALIBRATOR_PATH=str(tmp_path / "calibrator.json"),
        SAMPLES=3,
    )
    init_db(settings)
    session_factory = make_session_factory(settings)

    demo.generate_demo_data(session_factory, n_questions=80, seed=7)
    pipeline.forecast(session_factory, settings, FakeLLM())
    demo.simulate_outcomes(session_factory, seed=11)

    with session_factory() as session:
        forecasts = session.scalars(select(Forecast)).all()
        probs, outcomes = [], []
        for f in forecasts:
            q = session.get(Question, f.question_id)
            probs.append(f.raw_prob)
            outcomes.append(q.resolution)

    brier = scoring.brier_score(probs, outcomes)
    # No-skill fake model against independent coin-flip outcomes: expect
    # roughly 0.25, with slack for a finite, randomly-seeded sample.
    assert 0.15 < brier < 0.40
