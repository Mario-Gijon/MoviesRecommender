import json
from pathlib import Path

from app.core.config import settings
from app.infrastructure.catalog.catalog_models import (
    MovieCoverageNoteRecord,
    MovieGenreRecord,
    MovieRecord,
    MovieTagRecord,
)
from app.infrastructure.database.session import Base, SessionLocal, engine
from app.infrastructure.datasets.movielens_paths import ML_32M_DEMO_CATALOG_PATH


TMDB_POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
TMDB_BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/w780"


def main() -> None:
    if not ML_32M_DEMO_CATALOG_PATH.exists():
        raise RuntimeError(
            "Processed MovieLens 32M demo catalog is missing. "
            "Run `python -m app.scripts.build_demo_catalog_from_movielens_32m` first."
        )

    catalog = json.loads(ML_32M_DEMO_CATALOG_PATH.read_text(encoding="utf-8"))
    public_catalog = catalog.get("publicCatalog", [])
    collaborative_core = catalog.get("collaborativeCore", [])

    _ensure_sqlite_directory()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    public_by_movie_id = {item["movieId"]: item for item in public_catalog}
    collaborative_by_movie_id = {item["movieId"]: item for item in collaborative_core}
    public_order_by_movie_id = {item["movieId"]: index for index, item in enumerate(public_catalog)}
    collaborative_order_by_movie_id = {
        item["movieId"]: index for index, item in enumerate(collaborative_core)
    }

    all_movie_ids = list(dict.fromkeys(
        [item["movieId"] for item in public_catalog] + [item["movieId"] for item in collaborative_core]
    ))
    overlap_count = sum(1 for movie_id in all_movie_ids if movie_id in public_by_movie_id and movie_id in collaborative_by_movie_id)

    inserted_movies: list[MovieRecord] = []
    for movie_id in all_movie_ids:
        public_item = public_by_movie_id.get(movie_id)
        collaborative_item = collaborative_by_movie_id.get(movie_id)
        source_item = public_item or collaborative_item
        if source_item is None:
            continue

        inserted_movies.append(
            _build_movie_record(
                source_item=source_item,
                public_item=public_item,
                collaborative_item=collaborative_item,
                featured_order=public_order_by_movie_id.get(movie_id),
                recommendation_order=public_order_by_movie_id.get(movie_id),
                collaborative_order=collaborative_order_by_movie_id.get(movie_id),
            )
        )

    with SessionLocal() as session:
        session.add_all(inserted_movies)
        session.commit()

    print(f"Input JSON path: {ML_32M_DEMO_CATALOG_PATH}")
    print(f"Total unique movies inserted: {len(inserted_movies)}")
    print(f"Public catalog count: {len(public_catalog)}")
    print(f"Recommendation candidate count: {len(public_catalog)}")
    print(f"Collaborative core count: {len(collaborative_core)}")
    print(f"Public + collaborative overlap count: {overlap_count}")
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
    *,
    source_item: dict,
    public_item: dict | None,
    collaborative_item: dict | None,
    featured_order: int | None,
    recommendation_order: int | None,
    collaborative_order: int | None,
) -> MovieRecord:
    tags = _merge_tags(source_item)
    has_overview = bool(source_item.get("overview"))
    has_genres = bool(source_item.get("genres"))
    has_tags = bool(tags)
    has_poster = bool(source_item.get("posterPath"))
    has_certifications = bool(source_item.get("certifications"))
    rating_count = int(source_item.get("ratingCount") or 0)

    available_for_content = has_overview or has_genres or has_tags
    available_for_collaborative = collaborative_item is not None and rating_count > 0

    content_coverage = min(
        1.0,
        (0.25 if has_overview else 0.0)
        + (0.25 if has_genres else 0.0)
        + (0.25 if has_tags else 0.0)
        + (0.15 if has_poster else 0.0)
        + (0.10 if has_certifications else 0.0),
    )
    collaborative_coverage = min(1.0, rating_count / 250.0) if rating_count > 0 else 0.0

    movie = MovieRecord(
        id=source_item["movieId"],
        tmdb_id=source_item.get("tmdbId"),
        movie_lens_id=source_item["movieId"],
        imdb_id=source_item.get("imdbId"),
        title=source_item.get("cleanTitle") or source_item.get("title"),
        original_title=source_item.get("title"),
        year=source_item["year"],
        overview=source_item.get("overview"),
        poster_url=_build_image_url(TMDB_POSTER_BASE_URL, source_item.get("posterPath")),
        backdrop_url=_build_image_url(TMDB_BACKDROP_BASE_URL, source_item.get("backdropPath")),
        featured_order=featured_order,
        recommendation_order=recommendation_order,
        collaborative_order=collaborative_order,
        is_featured=public_item is not None,
        is_recommendation_candidate=public_item is not None,
        is_collaborative_core=collaborative_item is not None,
        available_for_content=available_for_content,
        available_for_collaborative=available_for_collaborative,
        content_coverage=round(content_coverage, 4),
        collaborative_coverage=round(collaborative_coverage, 4),
        demo_suitability=source_item.get("demoSuitability"),
        rating_count=rating_count or None,
        average_rating=source_item.get("averageRating"),
        candidate_score=source_item.get("candidateScore"),
        tmdb_popularity=source_item.get("tmdbPopularity"),
        tmdb_vote_average=source_item.get("tmdbVoteAverage"),
        tmdb_vote_count=source_item.get("tmdbVoteCount"),
        runtime=source_item.get("runtime"),
        original_language=source_item.get("originalLanguage"),
    )
    movie.genres = [MovieGenreRecord(name=name) for name in source_item.get("genres", [])]
    movie.tags = [MovieTagRecord(name=name) for name in tags]
    movie.coverage_notes = [
        MovieCoverageNoteRecord(note=note)
        for note in _build_coverage_notes(
            rating_count=rating_count,
            demo_suitability=source_item.get("demoSuitability"),
            is_public_movie=public_item is not None,
            is_collaborative_movie=collaborative_item is not None,
        )
    ]
    return movie


def _merge_tags(item: dict) -> list[str]:
    merged_tags: list[str] = []
    seen_tags: set[str] = set()

    for raw_tag in list(item.get("keywords", [])) + list(item.get("userTags", [])):
        normalized_tag = _normalize_tag(raw_tag)
        if not normalized_tag or normalized_tag in seen_tags:
            continue
        seen_tags.add(normalized_tag)
        merged_tags.append(normalized_tag)

    return merged_tags


def _normalize_tag(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _build_image_url(base_url: str, path: str | None) -> str | None:
    if not path:
        return None
    return f"{base_url}{path}"


def _build_coverage_notes(
    *,
    rating_count: int,
    demo_suitability: str | None,
    is_public_movie: bool,
    is_collaborative_movie: bool,
) -> list[str]:
    notes = [
        "Seeded from MovieLens 32M demo catalog",
        "TMDB metadata available",
        f"MovieLens collaborative rating count: {rating_count}",
        f"Demo suitability: {demo_suitability or 'unknown'}",
    ]
    if is_public_movie:
        notes.append("Public catalog movie")
    if is_collaborative_movie:
        notes.append("Collaborative core movie")
    return notes


if __name__ == "__main__":
    main()
