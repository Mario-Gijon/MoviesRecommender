from sqlalchemy import func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.infrastructure.catalog.catalog_mapper import movie_record_to_api_dict
from app.infrastructure.catalog.catalog_models import MovieGenreRecord, MovieRecord
from app.infrastructure.database.session import SessionLocal


class CatalogRepository:
    def get_status(self) -> dict:
        try:
            with SessionLocal() as session:
                total_movies = session.scalar(select(func.count(MovieRecord.id))) or 0
                if total_movies == 0:
                    return _build_uninitialized_status()

                visible_movies = session.scalar(
                    select(func.count(MovieRecord.id)).where(MovieRecord.is_featured.is_(True))
                ) or 0
                recommendable_movies = session.scalar(
                    select(func.count(MovieRecord.id)).where(MovieRecord.is_recommendation_candidate.is_(True))
                ) or 0
                avg_content = session.scalar(select(func.avg(MovieRecord.content_coverage))) or 0.0
                avg_collaborative = session.scalar(select(func.avg(MovieRecord.collaborative_coverage))) or 0.0
                hybrid_coverage = min(1.0, round((avg_content + avg_collaborative) / 2 + 0.11, 2))

                return {
                    "catalogVersion": "sqlite-demo-catalog-v1",
                    "totalMovies": total_movies,
                    "visibleMovies": visible_movies,
                    "recommendableMovies": recommendable_movies,
                    "contentCoverage": round(float(avg_content), 2),
                    "collaborativeCoverage": round(float(avg_collaborative), 2),
                    "hybridCoverage": hybrid_coverage,
                    "lastBuiltDate": None,
                    "dataMode": "sqlite-demo-catalog",
                    "sources": ["sqlite", "movielens", "tmdb"],
                    "notes": [
                        "SQLite stores the processed MovieLens/TMDB demo catalog.",
                        "Runtime API does not fetch external APIs.",
                        "TMDB images currently use CDN URLs for development.",
                        "Local image download and offline serving will come later.",
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

    def get_public_catalog_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        genre: str | None,
    ) -> tuple[list[dict], int]:
        try:
            with SessionLocal() as session:
                total_movies = session.scalar(select(func.count(MovieRecord.id))) or 0
                if total_movies == 0:
                    raise RuntimeError(
                        "Local catalog DB has not been initialized. "
                        "Run `python -m app.scripts.seed_placeholder_catalog` from Backend/."
                    )

                filtered_query = self._build_public_catalog_query(search=search, genre=genre)
                filtered_subquery = filtered_query.subquery()
                total_items = session.scalar(
                    select(func.count()).select_from(filtered_subquery)
                ) or 0

                paginated_query = (
                    filtered_query
                    .options(
                        selectinload(MovieRecord.genres),
                        selectinload(MovieRecord.tags),
                        selectinload(MovieRecord.coverage_notes),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                records = session.scalars(paginated_query).all()
                return [movie_record_to_api_dict(record) for record in records], int(total_items)
        except OperationalError as exc:
            raise RuntimeError(
                "Local catalog DB has not been initialized. "
                "Run `python -m app.scripts.seed_placeholder_catalog` from Backend/."
            ) from exc

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
                )
                if featured_only:
                    query = query.where(MovieRecord.is_featured.is_(True)).order_by(
                        MovieRecord.featured_order.asc().nullslast(),
                        MovieRecord.title.asc(),
                        MovieRecord.id.asc(),
                    )
                if recommendation_candidates_only:
                    query = query.where(MovieRecord.is_recommendation_candidate.is_(True)).order_by(
                        MovieRecord.recommendation_order.asc().nullslast(),
                        MovieRecord.title.asc(),
                        MovieRecord.id.asc(),
                    )
                if not featured_only and not recommendation_candidates_only:
                    query = query.order_by(MovieRecord.id.asc())

                records = session.scalars(query).all()
                if not records:
                    raise RuntimeError("Local catalog DB is initialized but contains no movies for the requested view.")
                return records
        except OperationalError as exc:
            raise RuntimeError(
                "Local catalog DB has not been initialized. "
                "Run `python -m app.scripts.seed_placeholder_catalog` from Backend/."
            ) from exc

    def _build_public_catalog_query(
        self,
        *,
        search: str | None,
        genre: str | None,
    ):
        query = select(MovieRecord).where(MovieRecord.is_featured.is_(True))

        if search and search.strip():
            normalized_search = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(MovieRecord.title).like(normalized_search),
                    func.lower(func.coalesce(MovieRecord.original_title, "")).like(normalized_search),
                    func.lower(func.coalesce(MovieRecord.display_title, "")).like(normalized_search),
                )
            )

        if genre and genre.strip():
            normalized_genre = genre.strip().lower()
            query = query.join(MovieRecord.genres).where(
                or_(
                    func.lower(MovieGenreRecord.name) == normalized_genre,
                    func.lower(func.coalesce(MovieGenreRecord.display_name, "")) == normalized_genre,
                )
            )

        return query.distinct().order_by(
            MovieRecord.featured_order.asc().nullslast(),
            MovieRecord.title.asc(),
            MovieRecord.id.asc(),
        )


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
