from pathlib import Path

from app.core.config import settings
from app.infrastructure.catalog.catalog_models import (
    MovieCoverageNoteRecord,
    MovieGenreRecord,
    MovieRecord,
    MovieTagRecord,
)
from app.infrastructure.database.session import Base, SessionLocal, engine
from app.infrastructure.datasets.movielens_paths import ML_LATEST_SMALL_DEMO_CATALOG_PATH


def main() -> None:
    if not ML_LATEST_SMALL_DEMO_CATALOG_PATH.exists():
        raise RuntimeError(
            "Demo catalog JSON is missing. "
            "Run `python -m app.scripts.build_demo_catalog_from_movielens_small` first."
        )

    _ensure_sqlite_directory()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    catalog = _load_demo_catalog()
    merged_movies = _merge_catalog_lists(catalog)

    with SessionLocal() as session:
        records = [_build_movie_record(movie) for movie in merged_movies.values()]
        session.add_all(records)
        session.commit()

    featured_count = sum(1 for movie in merged_movies.values() if movie["is_featured"])
    recommendation_count = sum(
        1 for movie in merged_movies.values() if movie["is_recommendation_candidate"]
    )
    collaborative_count = sum(
        1 for movie in merged_movies.values() if movie["is_collaborative_core"]
    )

    print(f"Input JSON path: {ML_LATEST_SMALL_DEMO_CATALOG_PATH}")
    print(f"Total unique movies inserted: {len(merged_movies)}")
    print(f"Featured count: {featured_count}")
    print(f"Recommendation candidate count: {recommendation_count}")
    print(f"Collaborative core count: {collaborative_count}")
    print(f"Database URL: {settings.database_url}")


def _ensure_sqlite_directory() -> None:
    sqlite_prefix = "sqlite:///"
    if not settings.database_url.startswith(sqlite_prefix):
        return

    sqlite_path = settings.database_url[len(sqlite_prefix):]
    if not sqlite_path or sqlite_path == ":memory:":
        return

    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)


def _load_demo_catalog() -> dict:
    import json

    return json.loads(ML_LATEST_SMALL_DEMO_CATALOG_PATH.read_text(encoding="utf-8"))


def _merge_catalog_lists(catalog: dict) -> dict[int, dict]:
    merged: dict[int, dict] = {}

    for index, item in enumerate(catalog.get("visibleMovies", [])):
        _merge_item(
            merged,
            item,
            is_featured=True,
            is_recommendation_candidate=False,
            is_collaborative_core=False,
            featured_order=index,
            recommendation_order=None,
            collaborative_order=None,
        )
    for index, item in enumerate(catalog.get("recommendationPool", [])):
        _merge_item(
            merged,
            item,
            is_featured=False,
            is_recommendation_candidate=True,
            is_collaborative_core=False,
            featured_order=None,
            recommendation_order=index,
            collaborative_order=None,
        )
    for index, item in enumerate(catalog.get("collaborativeCore", [])):
        _merge_item(
            merged,
            item,
            is_featured=False,
            is_recommendation_candidate=False,
            is_collaborative_core=True,
            featured_order=None,
            recommendation_order=None,
            collaborative_order=index,
        )

    return merged


def _merge_item(
    merged: dict[int, dict],
    item: dict,
    *,
    is_featured: bool,
    is_recommendation_candidate: bool,
    is_collaborative_core: bool,
    featured_order: int | None,
    recommendation_order: int | None,
    collaborative_order: int | None,
) -> None:
    movie_id = item["movieId"]
    existing = merged.get(movie_id)
    if existing is None:
        merged[movie_id] = {
            **item,
            "is_featured": is_featured,
            "is_recommendation_candidate": is_recommendation_candidate,
            "is_collaborative_core": is_collaborative_core,
            "featured_order": featured_order,
            "recommendation_order": recommendation_order,
            "collaborative_order": collaborative_order,
        }
        return

    existing["is_featured"] = existing["is_featured"] or is_featured
    existing["is_recommendation_candidate"] = (
        existing["is_recommendation_candidate"] or is_recommendation_candidate
    )
    existing["is_collaborative_core"] = (
        existing["is_collaborative_core"] or is_collaborative_core
    )
    if existing.get("featured_order") is None and featured_order is not None:
        existing["featured_order"] = featured_order
    if existing.get("recommendation_order") is None and recommendation_order is not None:
        existing["recommendation_order"] = recommendation_order
    if existing.get("collaborative_order") is None and collaborative_order is not None:
        existing["collaborative_order"] = collaborative_order

    for role in item.get("catalogRoles", []):
        if role not in existing["catalogRoles"]:
            existing["catalogRoles"].append(role)


def _build_movie_record(item: dict) -> MovieRecord:
    normalized_tags = _merge_tags(item.get("keywords", []), item.get("userTags", []))
    certifications = item.get("certifications", {})
    poster_url = _build_tmdb_image_url(item.get("posterPath"), "https://image.tmdb.org/t/p/w500")
    backdrop_url = _build_tmdb_image_url(item.get("backdropPath"), "https://image.tmdb.org/t/p/w780")
    available_for_content = bool(item.get("genres") or item.get("overview") or normalized_tags)
    available_for_collaborative = bool(
        item.get("is_collaborative_core") and (item.get("ratingCount") or 0) >= 20
    )
    content_coverage = _compute_content_coverage(
        overview=item.get("overview"),
        genres=item.get("genres", []),
        tags=normalized_tags,
        poster_url=poster_url,
        certifications=certifications,
    )
    collaborative_coverage = _compute_collaborative_coverage(item.get("ratingCount"))

    movie = MovieRecord(
        id=item["movieId"],
        tmdb_id=item.get("tmdbId"),
        movie_lens_id=item["movieId"],
        imdb_id=item.get("imdbId"),
        title=item.get("cleanTitle") or item.get("title"),
        original_title=item.get("title"),
        year=item.get("year") or 0,
        overview=item.get("overview"),
        poster_url=poster_url,
        backdrop_url=backdrop_url,
        featured_order=item.get("featured_order"),
        recommendation_order=item.get("recommendation_order"),
        collaborative_order=item.get("collaborative_order"),
        is_featured=item.get("is_featured", False),
        is_recommendation_candidate=item.get("is_recommendation_candidate", False),
        is_collaborative_core=item.get("is_collaborative_core", False),
        available_for_content=available_for_content,
        available_for_collaborative=available_for_collaborative,
        content_coverage=content_coverage,
        collaborative_coverage=collaborative_coverage,
        demo_suitability=item.get("demoSuitability"),
        rating_count=item.get("ratingCount"),
        average_rating=item.get("averageRating"),
        candidate_score=item.get("candidateScore"),
        tmdb_popularity=item.get("tmdbPopularity"),
        tmdb_vote_average=item.get("tmdbVoteAverage"),
        tmdb_vote_count=item.get("tmdbVoteCount"),
        runtime=item.get("runtime"),
        original_language=item.get("originalLanguage"),
    )
    movie.genres = [MovieGenreRecord(name=name) for name in item.get("genres", [])]
    movie.tags = [MovieTagRecord(name=name) for name in normalized_tags]
    movie.coverage_notes = [
        MovieCoverageNoteRecord(note=note)
        for note in _build_coverage_notes(item)
    ]
    return movie


def _merge_tags(keywords: list[str], user_tags: list[str]) -> list[str]:
    merged_tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in [*keywords, *user_tags]:
        normalized = " ".join(raw_tag.strip().lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged_tags.append(normalized)
    return merged_tags


def _build_tmdb_image_url(path: str | None, base_url: str) -> str | None:
    if not path:
        return None
    return f"{base_url}{path}"


def _compute_content_coverage(
    *,
    overview: str | None,
    genres: list[str],
    tags: list[str],
    poster_url: str | None,
    certifications: dict,
) -> float:
    score = 0.0
    if overview:
        score += 0.25
    if genres:
        score += 0.25
    if tags:
        score += 0.25
    if poster_url:
        score += 0.15
    if certifications:
        score += 0.10
    return min(1.0, round(score, 2))


def _compute_collaborative_coverage(rating_count: int | None) -> float:
    if not rating_count:
        return 0.0
    return min(1.0, round(rating_count / 250, 2))


def _build_coverage_notes(item: dict) -> list[str]:
    notes = [
        "Seeded from MovieLens latest-small demo catalog",
        "TMDB metadata available" if item.get("tmdbId") else "TMDB metadata unavailable",
        f"MovieLens collaborative rating count: {item.get('ratingCount') or 0}",
        f"Demo suitability: {item.get('demoSuitability')}",
    ]
    return notes


if __name__ == "__main__":
    main()
