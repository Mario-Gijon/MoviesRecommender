from app.core.config import settings


def get_database_url() -> str:
    return settings.sqlite_url

