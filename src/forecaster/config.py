from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FC_", env_file=".env", extra="ignore")

    LLM_PROVIDER: str = "fake"  # fake | anthropic | bedrock

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str | None = None

    BEDROCK_MODEL_ID: str | None = None
    AWS_REGION: str = "us-east-1"

    DATABASE_URL: str = "sqlite:///./data/forecaster.db"
    DB_SECRET_ARN: str | None = None
    DB_HOST: str | None = None
    DB_NAME: str = "forecaster"
    DB_PORT: int = 5432

    SAMPLES: int = 5
    TEMPERATURE: float = 0.7
    MAX_ARTICLES: int = 8
    LOOKBACK_DAYS: int = 14
    MAX_QUESTIONS: int = 25
    MIN_BETTORS: int = 10

    NEWS_PROVIDER: str = "gdelt"  # gdelt | newsapi
    NEWSAPI_KEY: str | None = None

    TRACK_RECORD_DIR: str = "./public"
    TRACK_RECORD_BUCKET: str | None = None
    CALIBRATOR_PATH: str = "./models/calibrator.json"

    ENABLE_DOCS: bool = False


def get_settings() -> Settings:
    return Settings()
