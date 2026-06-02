from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Movies Recommender API"
    app_version: str = "0.1.0"
    environment: str = "local"
    database_url: str = "sqlite:///./app/data/catalog.sqlite"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_prefix="MOVIES_RECOMMENDER_",
        case_sensitive=False,
    )


settings = Settings()
