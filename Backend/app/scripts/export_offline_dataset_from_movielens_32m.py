import csv
import json
from datetime import datetime, timezone

from app.infrastructure.datasets.movielens_paths import (
    ML_32M_DEMO_CATALOG_PATH,
    ML_32M_DEMO_RATINGS_BY_MOVIE_PATH,
    ML_32M_DEMO_RATINGS_PATH,
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_CSV_DIR,
    OFFLINE_DATASET_DIR,
    OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
    OFFLINE_DATASET_POSTERS_DIR,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)


LIST_SEPARATOR = "|"
COLLABORATIVE_RATINGS_COLUMNS = ["userId", "movieId", "rating", "timestamp"]
MOVIE_COLUMNS = [
    "movieId",
    "tmdbId",
    "imdbId",
    "title",
    "cleanTitle",
    "originalTitle",
    "displayTitle",
    "year",
    "overview",
    "displayOverview",
    "genres",
    "displayGenres",
    "keywords",
    "userTags",
    "topCast",
    "directors",
    "posterPath",
    "posterFile",
    "runtime",
    "originalLanguage",
    "ratingCount",
    "averageRating",
    "filteredRatingCount",
    "filteredAverageRating",
    "candidateScore",
    "dataReliabilityScore",
    "recencyScore",
    "tmdbPopularity",
    "tmdbVoteAverage",
    "tmdbVoteCount",
    "demoSuitability",
    "standDisplayScore",
]
EXCLUDED_MOVIE_COLUMNS = MOVIE_COLUMNS + [
    "exclusionCategory",
    "exclusionReasons",
    "suitabilityReasons",
    "publicExclusionReasons",
]
MOVIE_RATINGS_SUMMARY_COLUMNS = [
    "movieId",
    "title",
    "displayTitle",
    "datasetRole",
    "ratingCount",
    "averageRating",
    "filteredRatingCount",
    "filteredAverageRating",
]


def main() -> None:
    if not ML_32M_DEMO_CATALOG_PATH.exists():
        raise RuntimeError(
            "Run python -m app.scripts.build_demo_catalog_from_movielens_32m first."
        )

    if not ML_32M_DEMO_RATINGS_PATH.exists():
        raise RuntimeError(
            "Run python -m app.scripts.build_demo_ratings_from_movielens_32m first."
        )

    catalog = json.loads(ML_32M_DEMO_CATALOG_PATH.read_text(encoding="utf-8"))
    ratings_summary_by_movie = _load_ratings_summary_by_movie()

    OFFLINE_DATASET_DIR.mkdir(parents=True, exist_ok=True)
    OFFLINE_DATASET_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OFFLINE_DATASET_POSTERS_DIR.mkdir(parents=True, exist_ok=True)

    catalog_index = _build_catalog_index(catalog)

    public_rows = [
        _build_movie_csv_row(
            item,
            ratings_summary_by_movie=ratings_summary_by_movie,
        )
        for item in catalog_index["public_items"]
    ]
    support_rows = [
        _build_movie_csv_row(
            item,
            ratings_summary_by_movie=ratings_summary_by_movie,
        )
        for item in catalog_index["collaborative_support_items"]
    ]
    excluded_rows = [
        _build_excluded_movie_csv_row(
            item,
            ratings_summary_by_movie=ratings_summary_by_movie,
            public_ids=catalog_index["public_ids"],
            collaborative_support_ids=catalog_index["collaborative_support_ids"],
        )
        for item in catalog_index["excluded_items"]
    ]
    movie_ratings_summary_rows = _build_movie_ratings_summary_rows(
        public_items=catalog_index["public_items"],
        collaborative_support_items=catalog_index["collaborative_support_items"],
        ratings_summary_by_movie=ratings_summary_by_movie,
    )

    _write_csv(
        OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        MOVIE_COLUMNS,
        public_rows,
    )
    _write_csv(
        OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
        MOVIE_COLUMNS,
        support_rows,
    )
    _write_csv(
        OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
        EXCLUDED_MOVIE_COLUMNS,
        excluded_rows,
    )
    _write_csv(
        OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
        MOVIE_RATINGS_SUMMARY_COLUMNS,
        movie_ratings_summary_rows,
    )

    collaborative_ratings_written = _write_collaborative_ratings_csv(
        included_movie_ids=catalog_index["public_ids"] | catalog_index["collaborative_support_ids"]
    )
    manifest = _build_manifest(
        public_movies_count=len(public_rows),
        collaborative_support_movies_count=len(support_rows),
        excluded_movies_count=len(excluded_rows),
        collaborative_ratings_count=collaborative_ratings_written,
    )
    OFFLINE_DATASET_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(f"Input catalog path: {ML_32M_DEMO_CATALOG_PATH}")
    print(f"Input ratings path: {ML_32M_DEMO_RATINGS_PATH}")
    print(f"Output offline dataset dir: {OFFLINE_DATASET_DIR}")
    print(f"Public movies written: {len(public_rows)}")
    print(f"Collaborative support movies written: {len(support_rows)}")
    print(f"Excluded movies written: {len(excluded_rows)}")
    print(f"Collaborative ratings written: {collaborative_ratings_written}")
    print(f"Manifest path: {OFFLINE_DATASET_MANIFEST_PATH}")


def _build_catalog_index(catalog: dict) -> dict:
    public_items = list(catalog.get("publicCatalog", []))
    collaborative_items = list(catalog.get("collaborativeCore", []))
    excluded_source_items = list(catalog.get("excludedOrSensitive", []))

    public_ids = {
        movie_id
        for movie_id in (_parse_int(item.get("movieId")) for item in public_items)
        if movie_id is not None
    }

    merged_items_by_id: dict[int, dict] = {}
    ordered_all_ids: list[int] = []
    for items in (public_items, collaborative_items, excluded_source_items):
        for item in items:
            movie_id = _parse_int(item.get("movieId"))
            if movie_id is None:
                continue
            if movie_id not in merged_items_by_id:
                ordered_all_ids.append(movie_id)
                merged_items_by_id[movie_id] = dict(item)
                continue
            merged_items_by_id[movie_id] = {
                **merged_items_by_id[movie_id],
                **item,
            }

    unsafe_ids = {
        movie_id
        for movie_id, item in merged_items_by_id.items()
        if _is_unsafe_item(item)
    }

    collaborative_support_ids = []
    collaborative_support_id_set: set[int] = set()
    for item in collaborative_items:
        movie_id = _parse_int(item.get("movieId"))
        if movie_id is None or movie_id in public_ids or movie_id in unsafe_ids:
            continue
        if movie_id in collaborative_support_id_set:
            continue
        collaborative_support_ids.append(movie_id)
        collaborative_support_id_set.add(movie_id)

    excluded_id_set = {
        movie_id
        for movie_id in ordered_all_ids
        if movie_id not in public_ids and movie_id not in collaborative_support_id_set
    }
    excluded_id_set.update(unsafe_ids)
    excluded_id_set.difference_update(public_ids)
    excluded_id_set.difference_update(collaborative_support_id_set)

    public_items_by_id = _dedupe_items_by_id(public_items)
    collaborative_items_by_id = _dedupe_items_by_id(collaborative_items)

    public_rows_source = [public_items_by_id[movie_id] for movie_id in public_ids_in_order(public_items)]
    collaborative_support_items = [
        collaborative_items_by_id[movie_id]
        for movie_id in collaborative_support_ids
        if movie_id in collaborative_items_by_id
    ]
    excluded_items = [
        merged_items_by_id[movie_id]
        for movie_id in ordered_all_ids
        if movie_id in excluded_id_set
    ]

    return {
        "public_items": public_rows_source,
        "collaborative_support_items": collaborative_support_items,
        "excluded_items": excluded_items,
        "public_ids": public_ids,
        "collaborative_support_ids": collaborative_support_id_set,
    }


def public_ids_in_order(public_items: list[dict]) -> list[int]:
    ordered_ids: list[int] = []
    seen_ids: set[int] = set()
    for item in public_items:
        movie_id = _parse_int(item.get("movieId"))
        if movie_id is None or movie_id in seen_ids:
            continue
        seen_ids.add(movie_id)
        ordered_ids.append(movie_id)
    return ordered_ids


def _dedupe_items_by_id(items: list[dict]) -> dict[int, dict]:
    deduped: dict[int, dict] = {}
    for item in items:
        movie_id = _parse_int(item.get("movieId"))
        if movie_id is None or movie_id in deduped:
            continue
        deduped[movie_id] = item
    return deduped


def _is_unsafe_item(item: dict) -> bool:
    public_exclusion_reasons = {
        _normalize_reason(reason)
        for reason in item.get("publicExclusionReasons", [])
        if reason
    }
    demo_suitability = str(item.get("demoSuitability") or "").strip()
    enrichment_error = item.get("enrichmentError")

    return any(
        (
            demo_suitability == "adult_or_sensitive",
            demo_suitability == "unknown",
            bool(enrichment_error),
            "adult_or_sensitive" in public_exclusion_reasons,
            "unknown_suitability" in public_exclusion_reasons,
            "enrichment_error" in public_exclusion_reasons,
        )
    )


def _build_movie_csv_row(
    item: dict,
    *,
    ratings_summary_by_movie: dict[int, dict],
) -> dict:
    movie_id = _parse_int(item.get("movieId"))
    ratings_summary = ratings_summary_by_movie.get(movie_id, {})

    return {
        "movieId": movie_id or "",
        "tmdbId": _string_or_empty(item.get("tmdbId")),
        "imdbId": _string_or_empty(item.get("imdbId")),
        "title": _string_or_empty(item.get("title")),
        "cleanTitle": _string_or_empty(item.get("cleanTitle")),
        "originalTitle": _string_or_empty(item.get("originalTitle")),
        "displayTitle": _string_or_empty(item.get("displayTitle")),
        "year": _string_or_empty(item.get("year")),
        "overview": _string_or_empty(item.get("overview")),
        "displayOverview": _string_or_empty(item.get("displayOverview")),
        "genres": _join_list_values(item.get("genres", [])),
        "displayGenres": _join_list_values(item.get("displayGenres", [])),
        "keywords": _join_list_values(item.get("keywords", [])),
        "userTags": _join_list_values(item.get("userTags", [])),
        "topCast": _join_list_values(_extract_people_names(item.get("topCast", []))),
        "directors": _join_list_values(_extract_people_names(item.get("directors", []))),
        "posterPath": _string_or_empty(item.get("posterPath")),
        "posterFile": (
            f"images/posters/{movie_id}.jpg"
            if movie_id is not None and item.get("posterPath")
            else ""
        ),
        "runtime": _string_or_empty(item.get("runtime")),
        "originalLanguage": _string_or_empty(item.get("originalLanguage")),
        "ratingCount": _string_or_empty(item.get("ratingCount")),
        "averageRating": _string_or_empty(item.get("averageRating")),
        "filteredRatingCount": _string_or_empty(ratings_summary.get("filteredRatingCount")),
        "filteredAverageRating": _string_or_empty(ratings_summary.get("filteredAverageRating")),
        "candidateScore": _string_or_empty(item.get("candidateScore")),
        "dataReliabilityScore": _string_or_empty(item.get("dataReliabilityScore")),
        "recencyScore": _string_or_empty(item.get("recencyScore")),
        "tmdbPopularity": _string_or_empty(item.get("tmdbPopularity")),
        "tmdbVoteAverage": _string_or_empty(item.get("tmdbVoteAverage")),
        "tmdbVoteCount": _string_or_empty(item.get("tmdbVoteCount")),
        "demoSuitability": _string_or_empty(item.get("demoSuitability")),
        "standDisplayScore": _string_or_empty(item.get("standDisplayScore")),
    }


def _build_excluded_movie_csv_row(
    item: dict,
    *,
    ratings_summary_by_movie: dict[int, dict],
    public_ids: set[int],
    collaborative_support_ids: set[int],
) -> dict:
    row = _build_movie_csv_row(
        item,
        ratings_summary_by_movie=ratings_summary_by_movie,
    )
    exclusion_reasons = _build_exclusion_reasons(
        item,
        public_ids=public_ids,
        collaborative_support_ids=collaborative_support_ids,
    )
    row.update(
        {
            "exclusionCategory": _build_exclusion_category(exclusion_reasons),
            "exclusionReasons": _join_list_values(exclusion_reasons),
            "suitabilityReasons": _join_list_values(item.get("suitabilityReasons", [])),
            "publicExclusionReasons": _join_list_values(
                item.get("publicExclusionReasons", [])
            ),
        }
    )
    return row


def _build_exclusion_reasons(
    item: dict,
    *,
    public_ids: set[int],
    collaborative_support_ids: set[int],
) -> list[str]:
    reasons: list[str] = []
    movie_id = _parse_int(item.get("movieId"))
    public_exclusion_reasons = {
        _normalize_reason(reason)
        for reason in item.get("publicExclusionReasons", [])
        if reason
    }
    demo_suitability = str(item.get("demoSuitability") or "").strip()

    if demo_suitability == "adult_or_sensitive" or "adult_or_sensitive" in public_exclusion_reasons:
        reasons.append("adult_or_sensitive")
    if demo_suitability == "unknown" or "unknown_suitability" in public_exclusion_reasons:
        reasons.append("unknown_suitability")
    if item.get("enrichmentError") or "enrichment_error" in public_exclusion_reasons:
        reasons.append("enrichment_error")
    if movie_id not in public_ids and movie_id not in collaborative_support_ids:
        reasons.append("not_public_or_collaborative_support")

    return list(dict.fromkeys(reasons))


def _build_exclusion_category(exclusion_reasons: list[str]) -> str:
    if "adult_or_sensitive" in exclusion_reasons:
        return "sensitive_content"
    if "unknown_suitability" in exclusion_reasons:
        return "unknown_suitability"
    if "enrichment_error" in exclusion_reasons:
        return "enrichment_error"
    return "not_public_or_collaborative_support"


def _build_movie_ratings_summary_rows(
    *,
    public_items: list[dict],
    collaborative_support_items: list[dict],
    ratings_summary_by_movie: dict[int, dict],
) -> list[dict]:
    rows: list[dict] = []

    for dataset_role, items in (
        ("public", public_items),
        ("collaborative_support", collaborative_support_items),
    ):
        for item in items:
            movie_id = _parse_int(item.get("movieId"))
            ratings_summary = ratings_summary_by_movie.get(movie_id, {})
            rows.append(
                {
                    "movieId": movie_id or "",
                    "title": _string_or_empty(item.get("title")),
                    "displayTitle": _string_or_empty(item.get("displayTitle")),
                    "datasetRole": dataset_role,
                    "ratingCount": _string_or_empty(item.get("ratingCount")),
                    "averageRating": _string_or_empty(item.get("averageRating")),
                    "filteredRatingCount": _string_or_empty(
                        ratings_summary.get("filteredRatingCount")
                    ),
                    "filteredAverageRating": _string_or_empty(
                        ratings_summary.get("filteredAverageRating")
                    ),
                }
            )

    return rows


def _write_collaborative_ratings_csv(*, included_movie_ids: set[int]) -> int:
    rows_written = 0

    with ML_32M_DEMO_RATINGS_PATH.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        with OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as output_file:
            writer = csv.DictWriter(output_file, fieldnames=COLLABORATIVE_RATINGS_COLUMNS)
            writer.writeheader()

            for row in reader:
                movie_id = _parse_int(row.get("movieId"))
                if movie_id not in included_movie_ids:
                    continue

                writer.writerow(
                    {
                        "userId": row.get("userId", ""),
                        "movieId": row.get("movieId", ""),
                        "rating": row.get("rating", ""),
                        "timestamp": row.get("timestamp", ""),
                    }
                )
                rows_written += 1

    return rows_written


def _load_ratings_summary_by_movie() -> dict[int, dict]:
    if not ML_32M_DEMO_RATINGS_BY_MOVIE_PATH.exists():
        return {}

    summary_by_movie: dict[int, dict] = {}
    with ML_32M_DEMO_RATINGS_BY_MOVIE_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = _parse_int(row.get("movieId"))
            if movie_id is None:
                continue
            summary_by_movie[movie_id] = {
                "filteredRatingCount": row.get("filteredRatingCount", ""),
                "filteredAverageRating": row.get("filteredAverageRating", ""),
            }

    return summary_by_movie


def _build_manifest(
    *,
    public_movies_count: int,
    collaborative_support_movies_count: int,
    excluded_movies_count: int,
    collaborative_ratings_count: int,
) -> dict:
    return {
        "datasetName": "movies_recommender_offline_dataset",
        "schemaVersion": 1,
        "generatedAt": _utc_timestamp(),
        "sourceDataset": "MovieLens 32M",
        "metadataSource": "TMDB",
        "canonicalLanguage": "en-US",
        "displayLanguage": "es-ES",
        "listSeparator": LIST_SEPARATOR,
        "counts": {
            "publicMovies": public_movies_count,
            "collaborativeSupportMovies": collaborative_support_movies_count,
            "excludedMovies": excluded_movies_count,
            "collaborativeRatings": collaborative_ratings_count,
        },
        "files": {
            "publicMovies": "csv/public_movies.csv",
            "collaborativeSupportMovies": "csv/collaborative_support_movies.csv",
            "excludedMovies": "csv/excluded_movies.csv",
            "movieRatingsSummary": "csv/movie_ratings_summary.csv",
            "collaborativeRatings": "csv/collaborative_ratings.csv",
        },
        "images": {
            "postersDir": "images/posters",
            "posterNaming": "{movieId}.jpg",
            "backdrops": "not_included",
        },
        "notes": [
            "CSV is the portable offline dataset format.",
            "Posters are referenced locally and downloaded by download_offline_movie_posters.",
            "Backdrops are intentionally not included yet.",
            "SQLite is optional runtime cache, not the portable source of truth.",
            "Public movie selection and order come from the already processed publicCatalog.",
        ],
    }


def _write_csv(path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _extract_people_names(people: list[dict]) -> list[str]:
    names: list[str] = []
    for person in people:
        if isinstance(person, dict):
            names.append(person.get("name", ""))
            continue
        names.append(str(person))
    return names


def _join_list_values(values: list) -> str:
    sanitized_values = []
    for value in values:
        normalized = str(value).strip().replace(LIST_SEPARATOR, "/")
        if not normalized:
            continue
        sanitized_values.append(normalized)
    return LIST_SEPARATOR.join(sanitized_values)


def _normalize_reason(value: object) -> str:
    return str(value or "").strip()


def _parse_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _string_or_empty(value: object) -> str:
    if value in (None, ""):
        return ""
    return str(value)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
