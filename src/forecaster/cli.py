from __future__ import annotations

import typer
from sqlalchemy import select

from forecaster import demo as demo_module
from forecaster import opsdash, pipeline, scoring
from forecaster.config import get_settings
from forecaster.db import Forecast, Question, init_db, make_session_factory
from forecaster.llm import build_llm_client

app = typer.Typer(add_completion=False)


@app.command("init-db")
def init_db_cmd() -> None:
    settings = get_settings()
    init_db(settings)
    typer.echo("database initialized")


@app.command("ingest")
def ingest_cmd() -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    q_added, a_added = pipeline.ingest_questions(session_factory, settings)
    typer.echo(f"questions added: {q_added}")
    typer.echo(f"articles added: {a_added}")


@app.command("forecast")
def forecast_cmd() -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    llm_client = build_llm_client(settings)
    made = pipeline.forecast(session_factory, settings, llm_client)
    typer.echo(f"forecasts made: {made}")


@app.command("resolve")
def resolve_cmd() -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    resolved = pipeline.resolve(session_factory, settings)
    typer.echo(f"resolved {resolved}")


@app.command("publish")
def publish_cmd() -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    pipeline.publish(session_factory, settings)
    typer.echo(f"published to {settings.TRACK_RECORD_DIR}")


@app.command("daily")
def daily_cmd() -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    llm_client = build_llm_client(settings)
    result = pipeline.daily(session_factory, settings, llm_client)
    typer.echo(f"resolved {result['resolved']}")
    typer.echo(f"questions added: {result['questions_added']}")
    typer.echo(f"articles added: {result['articles_added']}")
    typer.echo(f"forecasts made: {result['forecasts_made']}")


@app.command("calibrate")
def calibrate_cmd(method: str = typer.Option("auto", "--method")) -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    n_train = pipeline.calibrate(session_factory, settings, method=method)
    typer.echo(
        f"calibrator fit on {n_train} resolved forecasts, written to {settings.CALIBRATOR_PATH}"
    )


@app.command("demo")
def demo_cmd(questions: int = typer.Option(100, "--questions")) -> None:
    settings = get_settings()
    init_db(settings)
    session_factory = make_session_factory(settings)
    llm_client = build_llm_client(settings)

    demo_module.generate_demo_data(session_factory, questions)
    made = pipeline.forecast(session_factory, settings, llm_client)
    demo_module.simulate_outcomes(session_factory)
    pipeline.calibrate(session_factory, settings)
    pipeline.publish(session_factory, settings)

    with session_factory() as session:
        rows = session.scalars(select(Forecast)).all()
        probs, outcomes = [], []
        for f in rows:
            q = session.get(Question, f.question_id)
            if q and q.resolution is not None:
                probs.append(f.raw_prob)
                outcomes.append(q.resolution)

    brier = scoring.brier_score(probs, outcomes) if probs else float("nan")
    typer.echo(f"demo: {questions} fictional questions, {made} forecasts made")
    typer.echo(f"brier score (no-skill fake model, expect ~0.25): {brier:.3f}")
    typer.echo(f"site written to {settings.TRACK_RECORD_DIR}/index.html")


@app.command("dashboard")
def dashboard_cmd(output_dir: str = typer.Option("./ops", "--output-dir")) -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    path = opsdash.render_dashboard(session_factory, settings, output_dir)
    typer.echo(f"local ops dashboard written to {path} (not published, not committed)")


if __name__ == "__main__":
    app()
