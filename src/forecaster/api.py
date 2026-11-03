from __future__ import annotations

from fastapi import FastAPI, HTTPException
from sqlalchemy import select

from forecaster.config import get_settings
from forecaster.db import Forecast, Question, make_session_factory

settings = get_settings()
session_factory = make_session_factory(settings)

app = FastAPI(
    title="LLM Forecast Pipeline API",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url=None,
)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/questions")
def list_questions(status: str | None = None) -> list[dict]:
    with session_factory() as session:
        stmt = select(Question)
        if status:
            stmt = stmt.where(Question.status == status)
        rows = session.scalars(stmt).all()
        return [
            {
                "id": q.id,
                "title": q.title,
                "url": q.url,
                "status": q.status,
                "close_time": q.close_time,
                "market_prob": q.market_prob,
                "resolution": q.resolution,
            }
            for q in rows
        ]


@app.get("/forecasts/{question_id:path}")
def list_forecasts(question_id: str) -> list[dict]:
    with session_factory() as session:
        rows = session.scalars(
            select(Forecast)
            .where(Forecast.question_id == question_id)
            .order_by(Forecast.created_at)
        ).all()
        if not rows:
            raise HTTPException(status_code=404, detail="no forecasts for this question")
        return [
            {
                "created_at": f.created_at,
                "model": f.model,
                "prompt_version": f.prompt_version,
                "raw_prob": f.raw_prob,
                "calibrated_prob": f.calibrated_prob,
                "calibrator_version": f.calibrator_version,
            }
            for f in rows
        ]


@app.get("/track-record")
def track_record() -> list[dict]:
    with session_factory() as session:
        questions = session.scalars(select(Question)).all()
        result = []
        for q in questions:
            rows = session.scalars(
                select(Forecast).where(Forecast.question_id == q.id).order_by(Forecast.created_at)
            ).all()
            if not rows:
                continue
            latest = rows[-1]
            result.append(
                {
                    "id": q.id,
                    "title": q.title,
                    "status": q.status,
                    "resolution": q.resolution,
                    "latest_prob": latest.calibrated_prob
                    if latest.calibrated_prob is not None
                    else latest.raw_prob,
                    "forecast_count": len(rows),
                }
            )
        return result
