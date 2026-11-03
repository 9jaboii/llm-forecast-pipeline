from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from forecaster.config import Settings


class Base(DeclarativeBase):
    pass


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "manifold:abc123"
    source: Mapped[str] = mapped_column(String, default="manifold")
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    close_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    market_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")  # open | resolved
    resolution: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    articles: Mapped[list[Article]] = relationship(back_populates="question")
    forecasts: Mapped[list[Forecast]] = relationship(back_populates="question")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)

    question: Mapped[Question] = relationship(back_populates="articles")


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    model: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    prompt_sha256: Mapped[str] = mapped_column(String)
    samples: Mapped[list] = mapped_column(JSON)  # raw per-sample probabilities
    raw_prob: Mapped[float] = mapped_column(Float)
    calibrated_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrator_version: Mapped[str | None] = mapped_column(String, nullable=True)
    rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)

    question: Mapped[Question] = relationship(back_populates="forecasts")


def resolve_database_url(settings: Settings) -> str:
    """Local .env sets DATABASE_URL directly. In-cluster, DB_SECRET_ARN is set
    instead and the password is fetched from Secrets Manager at process start."""
    if not settings.DB_SECRET_ARN:
        return settings.DATABASE_URL

    import boto3

    client = boto3.client("secretsmanager", region_name=settings.AWS_REGION)
    secret = json.loads(client.get_secret_value(SecretId=settings.DB_SECRET_ARN)["SecretString"])
    user = secret["username"]
    password = secret["password"]
    return f"postgresql+psycopg://{user}:{password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"


def make_session_factory(settings: Settings) -> sessionmaker[Session]:
    url = resolve_database_url(settings)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    return sessionmaker(bind=engine)


def init_db(settings: Settings) -> None:
    url = resolve_database_url(settings)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(engine)
