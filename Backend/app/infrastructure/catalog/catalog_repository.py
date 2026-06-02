from sqlalchemy.exc import OperationalError
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.infrastructure.catalog.catalog_mapper import movie_record_to_api_dict
from app.infrastructure.catalog.catalog_models import MovieRecord
from app.infrastructure.database.session import SessionLocal


class CatalogRepository:
    def get_status(self) -> dict:
        try:
            with SessionLocal() as session:
                total_movies = session.scalar(select(func.count(MovieRecord.id))) or 0
                if total_movies == 0:
                    return _build_uninitialized_status()

                visible_movies = total_movies
                recommendable_movies = session.scalar(
                    select(func.count(MovieRecord.id)).where(MovieRecord.is_recommendation_candidate.is_(True))
                ) or 0
                avg_content = session.scalar(select(func.avg(MovieRecord.content_coverage))) or 0.0
                avg_collaborative = session.scalar(select(func.avg(MovieRecord.collaborative_coverage))) or 0.0
                hybrid_coverage = min(1.0, round((avg_content + avg_collaborative) / 2 + 0.11, 2))

                return {
                    "catalogVersion": "sqlite-placeholder-v1",
                    "totalMovies": total_movies,
                    "visibleMovies": visible_movies,
                    "recommendableMovies": recommendable_movies,
                    "contentCoverage": round(float(avg_content), 2),
                    "collaborativeCoverage": round(float(avg_collaborative), 2),
                    "hybridCoverage": hybrid_coverage,
                    "lastBuiltDate": None,
                    "dataMode": "sqlite-placeholder",
                    "sources": ["sqlite", "placeholder"],
                    "notes": [
                        "SQLite currently stores placeholder catalog data only.",
                        "Runtime API does not fetch external APIs.",
                        "Real TMDB and MovieLens offline catalog build steps will replace this seed later.",
                    ],
                }
        except OperationalError:
            return _build_uninitialized_status()

    def get_featured_movies(self) -> list[dict]:
        records = self._load_movies(featured_only=True)
        return [movie_record_to_api_dict(record) for record in records]

    def get_recommendation_candidates(self) -> list[dict]:
        records = self._load_movies(recommendation_candidates_only=True)
        return [movie_record_to_api_dict(record) for record in records]

    def _load_movies(
        self,
        *,
        featured_only: bool = False,
        recommendation_candidates_only: bool = False,
    ) -> list[MovieRecord]:
        try:
            with SessionLocal() as session:
                total_movies = session.scalar(select(func.count(MovieRecord.id))) or 0
                if total_movies == 0:
                    raise RuntimeError(
                        "Local catalog DB has not been initialized. "
                        "Run `python -m app.scripts.seed_placeholder_catalog` from Backend/."
                    )

                query = (
                    select(MovieRecord)
                    .options(
                        selectinload(MovieRecord.genres),
                        selectinload(MovieRecord.tags),
                        selectinload(MovieRecord.coverage_notes),
                    )
                    .order_by(MovieRecord.id)
                )
                if featured_only:
                    query = query.where(MovieRecord.is_featured.is_(True))
                if recommendation_candidates_only:
                    query = query.where(MovieRecord.is_recommendation_candidate.is_(True))

                records = session.scalars(query).all()
                if not records:
                    raise RuntimeError("Local catalog DB is initialized but contains no movies for the requested view.")
                return records
        except OperationalError as exc:
            raise RuntimeError(
                "Local catalog DB has not been initialized. "
                "Run `python -m app.scripts.seed_placeholder_catalog` from Backend/."
            ) from exc


def _build_uninitialized_status() -> dict:
    return {
        "catalogVersion": "uninitialized",
        "totalMovies": 0,
        "visibleMovies": 0,
        "recommendableMovies": 0,
        "contentCoverage": 0.0,
        "collaborativeCoverage": 0.0,
        "hybridCoverage": 0.0,
        "lastBuiltDate": None,
        "dataMode": "uninitialized",
        "sources": ["sqlite"],
        "notes": [
            "Local SQLite catalog has not been initialized.",
            "Run python -m app.scripts.seed_placeholder_catalog from Backend/ to seed placeholder data.",
            f"Configured database URL: {settings.database_url}",
        ],
    }


catalog_repository = CatalogRepository()
