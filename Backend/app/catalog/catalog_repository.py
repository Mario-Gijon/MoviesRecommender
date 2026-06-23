import csv
import json

from app.project_paths.dataset_paths import (
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_POSTERS_DIR,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)


EXPORT_DATASET_COMMAND = "python -m pipelines.dataset_generation.export_offline_dataset_from_movielens_32m"
POSTER_URL_PREFIX = "/offline/posters"
LIST_SEPARATOR = "|"


class OfflineCatalogRepository:
    def __init__(self) -> None:
        self._manifest = self._load_manifest()
        self._public_movies = self._load_public_movies()
        self._public_movies_by_id = {
            int(movie["movieId"]): movie for movie in self._public_movies
        }

    def get_status(self) -> dict:
        total_movies = len(self._public_movies)
        average_content_coverage = _round_float(
            _average(movie["coverage"]["contentCoverage"] for movie in self._public_movies)
        )
        average_collaborative_coverage = _round_float(
            _average(movie["coverage"]["collaborativeCoverage"] for movie in self._public_movies)
        )
        hybrid_coverage = min(
            1.0,
            round((average_content_coverage + average_collaborative_coverage) / 2 + 0.11, 2),
        )

        dataset_name = str(self._manifest.get("datasetName") or "offline-dataset")
        schema_version = self._manifest.get("schemaVersion") or 1

        return {
            "catalogVersion": f"{dataset_name}-v{schema_version}",
            "totalMovies": total_movies,
            "visibleMovies": total_movies,
            "recommendableMovies": total_movies,
            "contentCoverage": average_content_coverage,
            "collaborativeCoverage": average_collaborative_coverage,
            "hybridCoverage": hybrid_coverage,
            "lastBuiltDate": self._manifest.get("generatedAt"),
            "dataMode": "offline-csv-dataset",
            "sources": ["offline_dataset", "movielens", "tmdb"],
            "notes": [
                "Runtime catalog is loaded from the portable offline CSV dataset.",
                "Posters are served locally from /offline/posters.",
                "No external APIs are used at runtime.",
            ],
        }

    def get_featured_movies(self) -> list[dict]:
        return list(self._public_movies)

    def get_recommendation_candidates(self) -> list[dict]:
        return list(self._public_movies)

    def get_public_movie_by_id(self, movie_id: int) -> dict:
        movie = self._public_movies_by_id.get(movie_id)
        if movie is None:
            raise RuntimeError(
                f"Public movie with movieId {movie_id} was not found in the offline public catalog."
            )
        return movie

    def get_public_catalog_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        genre: str | None,
    ) -> tuple[list[dict], int]:
        filtered_movies = [
            movie for movie in self._public_movies if self._matches_filters(movie, search=search, genre=genre)
        ]
        total_items = len(filtered_movies)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        return filtered_movies[start_index:end_index], total_items

    def _load_manifest(self) -> dict:
        if not OFFLINE_DATASET_MANIFEST_PATH.exists():
            return {}
        return json.loads(OFFLINE_DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))

    def _load_public_movies(self) -> list[dict]:
        if not OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH.exists():
            raise RuntimeError(
                "Offline public catalog CSV is missing. "
                f"Run {EXPORT_DATASET_COMMAND} first."
            )

        movies: list[dict] = []
        with OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                movie = _build_movie_from_csv_row(row)
                if movie is None:
                    continue
                movies.append(movie)

        if not movies:
            raise RuntimeError(
                "Offline public catalog CSV contains no public movies. "
                f"Run {EXPORT_DATASET_COMMAND} first."
            )

        return movies

    def _matches_filters(
        self,
        movie: dict,
        *,
        search: str | None,
        genre: str | None,
    ) -> bool:
        if search and search.strip():
            normalized_search = search.strip().lower()
            haystack = [
                _normalize_text(movie.get("title")),
                _normalize_text(movie.get("displayTitle")),
            ]
            if not any(normalized_search in value for value in haystack if value):
                return False

        if genre and genre.strip():
            normalized_genre = genre.strip().lower()
            canonical_genres = {_normalize_text(value) for value in movie.get("genres", [])}
            display_genres = {
                _normalize_text(value) for value in movie.get("displayGenres", []) or []
            }
            if normalized_genre not in canonical_genres and normalized_genre not in display_genres:
                return False

        return True


def _build_movie_from_csv_row(row: dict[str, str]) -> dict | None:
    movie_id = _parse_int(row.get("movieId"))
    year = _parse_int(row.get("year"))
    if movie_id is None or year is None:
        return None

    title = _string_or_none(row.get("cleanTitle")) or _string_or_none(row.get("title"))
    if not title:
        return None

    genres = _split_list_field(row.get("genres"))
    display_genres = _split_list_field(row.get("displayGenres"))
    keywords = _split_list_field(row.get("keywords"))
    user_tags = _split_list_field(row.get("userTags"))
    tags = _merge_unique_values(keywords + user_tags)
    overview = _string_or_none(row.get("overview"))
    filtered_rating_count = _parse_int(row.get("filteredRatingCount"))
    rating_count = _parse_int(row.get("ratingCount"))
    available_for_content = bool(genres or keywords or user_tags or overview)
    available_for_collaborative = (filtered_rating_count or rating_count or 0) > 0
    content_coverage = _build_content_coverage(
        overview=overview,
        genres=genres,
        keywords=keywords,
        user_tags=user_tags,
    )
    collaborative_coverage = _build_collaborative_coverage(
        filtered_rating_count=filtered_rating_count,
        rating_count=rating_count,
    )
    poster_url = _build_local_poster_url(
        movie_id=movie_id,
        poster_file=row.get("posterFile", ""),
    )

    coverage_notes = ["Offline dataset"]
    if poster_url:
        coverage_notes.append("Local poster available")
    if available_for_content:
        coverage_notes.append("Content metadata available")
    if available_for_collaborative:
        coverage_notes.append("Collaborative ratings available")

    return {
        "movieId": movie_id,
        "id": movie_id,
        "tmdbId": _parse_int(row.get("tmdbId")),
        "movieLensId": movie_id,
        "imdbId": _string_or_none(row.get("imdbId")),
        "title": title,
        "cleanTitle": _string_or_none(row.get("cleanTitle")),
        "originalTitle": _string_or_none(row.get("originalTitle")) or _string_or_none(row.get("title")),
        "year": year,
        "overview": overview,
        "displayTitle": _string_or_none(row.get("displayTitle")) or title,
        "displayOverview": _string_or_none(row.get("displayOverview")) or overview,
        "posterPath": _string_or_none(row.get("posterPath")),
        "posterFile": _string_or_none(row.get("posterFile")),
        "posterUrl": poster_url,
        "runtime": _parse_int(row.get("runtime")),
        "originalLanguage": _string_or_none(row.get("originalLanguage")),
        "genres": genres,
        "displayGenres": display_genres,
        "keywords": keywords,
        "userTags": user_tags,
        "topCast": _split_list_field(row.get("topCast")),
        "directors": _split_list_field(row.get("directors")),
        "tags": tags,
        "ratingCount": rating_count,
        "averageRating": _parse_float(row.get("averageRating")),
        "filteredRatingCount": filtered_rating_count,
        "filteredAverageRating": _parse_float(row.get("filteredAverageRating")),
        "candidateScore": _parse_float(row.get("candidateScore")),
        "dataReliabilityScore": _parse_float(row.get("dataReliabilityScore")),
        "recencyScore": _parse_float(row.get("recencyScore")),
        "tmdbPopularity": _parse_float(row.get("tmdbPopularity")),
        "tmdbVoteAverage": _parse_float(row.get("tmdbVoteAverage")),
        "tmdbVoteCount": _parse_int(row.get("tmdbVoteCount")),
        "suitabilityCategory": _string_or_none(row.get("suitabilityCategory")),
        "standDisplayScore": _parse_float(row.get("standDisplayScore")),
        "standDisplayReasons": _split_list_field(row.get("standDisplayReasons")),
        "coverage": {
            "availableForContent": available_for_content,
            "availableForCollaborative": available_for_collaborative,
            "contentCoverage": content_coverage,
            "collaborativeCoverage": collaborative_coverage,
            "coverageNotes": coverage_notes,
        },
    }


def _build_local_poster_url(*, movie_id: int, poster_file: str | None) -> str | None:
    if not _string_or_none(poster_file):
        return None

    poster_path = OFFLINE_DATASET_POSTERS_DIR / f"{movie_id}.jpg"
    if not poster_path.exists():
        return None

    return f"{POSTER_URL_PREFIX}/{movie_id}.jpg"


def _build_content_coverage(
    *,
    overview: str | None,
    genres: list[str],
    keywords: list[str],
    user_tags: list[str],
) -> float:
    coverage = 0.0
    if overview:
        coverage += 0.35
    if genres:
        coverage += 0.25
    if keywords:
        coverage += 0.2
    if user_tags:
        coverage += 0.2
    return round(min(1.0, coverage), 4)


def _build_collaborative_coverage(
    *,
    filtered_rating_count: int | None,
    rating_count: int | None,
) -> float:
    rating_volume = filtered_rating_count if filtered_rating_count is not None else rating_count or 0
    return round(min(1.0, rating_volume / 250.0), 4)


def _split_list_field(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(LIST_SEPARATOR) if item.strip()]


def _merge_unique_values(values: list[str]) -> list[str]:
    merged_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        normalized_value = value.strip()
        if not normalized_value:
            continue
        key = normalized_value.lower()
        if key in seen_values:
            continue
        seen_values.add(key)
        merged_values.append(normalized_value)
    return merged_values


def _average(values) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _parse_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _round_float(value: float) -> float:
    return round(float(value), 2)


catalog_repository = OfflineCatalogRepository()
