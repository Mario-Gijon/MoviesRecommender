from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Movies Recommender API"
    app_version: str = "0.1.0"
    environment: str = "local"
    tmdb_bearer_token: str | None = None
    active_collaborative_algorithm: str = "popularity_baseline"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_prefix="MOVIES_RECOMMENDER_",
        case_sensitive=False,
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
    )


settings = Settings()