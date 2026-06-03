from pathlib import Path

from app.core.config import settings
from app.infrastructure.catalog.catalog_models import (
    MovieCoverageNoteRecord,
    MovieGenreRecord,
    MovieRecord,
    MovieTagRecord,
)
from app.infrastructure.catalog.placeholder_catalog import (
    PLACEHOLDER_FEATURED_MOVIES,
    PLACEHOLDER_RECOMMENDATION_CANDIDATES,
)
from app.infrastructure.database.session import Base, SessionLocal, engine


def main() -> None:
    _ensure_sqlite_directory()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        inserted_movies = [
            _build_movie_record(
                movie_data,
                is_featured=True,
                is_recommendation_candidate=False,
                featured_order=index,
                recommendation_order=None,
            )
            for index, movie_data in enumerate(PLACEHOLDER_FEATURED_MOVIES)
        ] + [
            _build_movie_record(
                movie_data,
                is_featured=False,
                is_recommendation_candidate=True,
                featured_order=None,
                recommendation_order=index,
            )
            for index, movie_data in enumerate(PLACEHOLDER_RECOMMENDATION_CANDIDATES)
        ]

        session.add_all(inserted_movies)
        session.commit()

    print(f"Inserted {len(inserted_movies)} movies")
    print(f"Featured count: {len(PLACEHOLDER_FEATURED_MOVIES)}")
    print(f"Recommendation candidate count: {len(PLACEHOLDER_RECOMMENDATION_CANDIDATES)}")
    print(f"Database URL: {settings.database_url}")


def _ensure_sqlite_directory() -> None:
    sqlite_prefix = "sqlite:///"
    if not settings.database_url.startswith(sqlite_prefix):
        return

    sqlite_path = settings.database_url[len(sqlite_prefix):]
    if not sqlite_path or sqlite_path == ":memory:":
        return

    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)


def _build_movie_record(
    movie_data: dict,
    *,
    is_featured: bool,
    is_recommendation_candidate: bool,
    featured_order: int | None,
    recommendation_order: int | None,
) -> MovieRecord:
    coverage = movie_data["coverage"]
    movie = MovieRecord(
        id=movie_data["id"],
        tmdb_id=movie_data["tmdbId"],
        movie_lens_id=movie_data["movieLensId"],
        imdb_id=movie_data["imdbId"],
        title=movie_data["title"],
        original_title=movie_data["originalTitle"],
        year=movie_data["year"],
        overview=movie_data["overview"],
        poster_url=movie_data["posterUrl"],
        featured_order=featured_order,
        recommendation_order=recommendation_order,
        is_featured=is_featured,
        is_recommendation_candidate=is_recommendation_candidate,
        available_for_content=coverage["availableForContent"],
        available_for_collaborative=coverage["availableForCollaborative"],
        content_coverage=coverage["contentCoverage"],
        collaborative_coverage=coverage["collaborativeCoverage"],
    )
    movie.genres = [MovieGenreRecord(name=name) for name in movie_data["genres"]]
    movie.tags = [MovieTagRecord(name=name) for name in movie_data["tags"]]
    movie.coverage_notes = [
        MovieCoverageNoteRecord(note=note)
        for note in coverage["coverageNotes"]
    ]
    return movie


if __name__ == "__main__":
    main()
