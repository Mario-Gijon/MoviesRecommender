import csv
import json
from datetime import datetime, timezone

from app.project_paths.dataset_paths import (
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
from app.catalog.constants import PUBLIC_MIN_RUNTIME_MINUTES


LIST_SEPARATOR = "|"
COLLABORATIVE_RATINGS_COLUMNS = ["userId", "movieId", "rating", "timestamp"]
BASE_MOVIE_COLUMNS = [
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
    "suitabilityCategory",
    "standDisplayScore",
    "standDisplayReasons",
]
PUBLIC_MOVIE_COLUMNS = list(BASE_MOVIE_COLUMNS)
SUPPORT_MOVIE_COLUMNS = BASE_MOVIE_COLUMNS + [
    "publicExclusionReasons",
    "publicBlockedTerms",
    "suitabilityReasons",
]
EXCLUDED_MOVIE_COLUMNS = SUPPORT_MOVIE_COLUMNS + [
    "exclusionCategory",
    "exclusionReasons",
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
            "Run python -m pipelines.dataset_generation.build_demo_catalog_from_movielens_32m first."
        )

    if not ML_32M_DEMO_RATINGS_PATH.exists():
        raise RuntimeError(
            "Run python -m pipelines.dataset_generation.build_demo_ratings_from_movielens_32m first."
        )

    catalog = json.loads(ML_32M_DEMO_CATALOG_PATH.read_text(encoding="utf-8"))
    ratings_summary_by_movie, has_ratings_summary = _load_ratings_summary_by_movie()

    OFFLINE_DATASET_DIR.mkdir(parents=True, exist_ok=True)
    OFFLINE_DATASET_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OFFLINE_DATASET_POSTERS_DIR.mkdir(parents=True, exist_ok=True)

    catalog_index = _build_catalog_index(
        catalog,
        ratings_summary_by_movie=ratings_summary_by_movie,
        has_ratings_summary=has_ratings_summary,
    )

    public_rows = [
        _build_public_movie_csv_row(
            item,
            ratings_summary_by_movie=ratings_summary_by_movie,
        )
        for item in catalog_index["public_items"]
    ]
    support_rows = [
        _build_support_movie_csv_row(
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
            has_ratings_summary=has_ratings_summary,
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
        PUBLIC_MOVIE_COLUMNS,
        public_rows,
    )
    _write_csv(
        OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
        SUPPORT_MOVIE_COLUMNS,
        support_rows,
    )
    # Preserve the original non-audience eligibility decision for later offline
    # audience-policy reconfiguration.  Import locally to avoid a module cycle.
    from .reconfigure_offline_dataset import CATALOG_COLUMNS
    catalog_rows = []
    for row in public_rows + support_rows:
        reasons = [part for part in row.get("publicExclusionReasons", "").split(LIST_SEPARATOR) if part]
        base_reasons = [reason for reason in reasons if reason not in {"adult_or_sensitive", "unknown_suitability", "family_only_excludes_teen"}]
        catalog_rows.append({
            **{column: row.get(column, "") for column in SUPPORT_MOVIE_COLUMNS},
            "basePublicEligible": "true" if row in public_rows or not base_reasons else "false",
            "basePublicExclusionReasons": LIST_SEPARATOR.join(base_reasons),
            "audiencePolicyExclusionReason": "",
        })
    _write_csv(OFFLINE_DATASET_CSV_DIR / "catalog_movies.csv", CATALOG_COLUMNS, catalog_rows)
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
        public_audience_policy=catalog.get("summary", {}).get("publicAudiencePolicy", "family_and_teen"),
        minimum_runtime_minutes=PUBLIC_MIN_RUNTIME_MINUTES,
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


def _build_catalog_index(
    catalog: dict,
    *,
    ratings_summary_by_movie: dict[int, dict],
    has_ratings_summary: bool,
) -> dict:
    public_items = list(catalog.get("publicCatalog", []))
    collaborative_items = list(catalog.get("collaborativeCore", []))
    excluded_source_items = list(catalog.get("excludedOrSensitive", []))

    merged_items_by_id: dict[int, dict] = {}
    public_ids: set[int] = set()
    ordered_all_entries: list[tuple[str, int]] = []
    invalid_items: list[dict] = []
    invalid_item_fingerprints: set[tuple[str, str, str, str]] = set()

    for items in (public_items, collaborative_items, excluded_source_items):
        for item in items:
            movie_id = _parse_int(item.get("movieId"))
            if movie_id is None:
                fingerprint = _build_invalid_item_fingerprint(item)
                if fingerprint in invalid_item_fingerprints:
                    continue
                invalid_item_fingerprints.add(fingerprint)
                invalid_items.append(dict(item))
                ordered_all_entries.append(("invalid", len(invalid_items) - 1))
                continue
            if movie_id not in merged_items_by_id:
                ordered_all_entries.append(("movie", movie_id))
                merged_items_by_id[movie_id] = dict(item)
                continue
            merged_items_by_id[movie_id] = {
                **merged_items_by_id[movie_id],
                **item,
            }

    public_ordered_ids = _movie_ids_in_order(public_items)
    public_ids.update(public_ordered_ids)

    collaborative_support_ids: list[int] = []
    collaborative_support_id_set: set[int] = set()
    for item in collaborative_items:
        movie_id = _parse_int(item.get("movieId"))
        merged_item = merged_items_by_id.get(movie_id) if movie_id is not None else item
        if movie_id is None or movie_id in public_ids:
            continue
        if movie_id in collaborative_support_id_set:
            continue
        if _is_technically_invalid_support_item(
            merged_item,
            ratings_summary_by_movie=ratings_summary_by_movie,
            has_ratings_summary=has_ratings_summary,
        ):
            continue
        collaborative_support_ids.append(movie_id)
        collaborative_support_id_set.add(movie_id)

    public_items_by_id = _dedupe_items_by_id(public_items)
    collaborative_items_by_id = _dedupe_items_by_id(collaborative_items)

    public_rows_source = [public_items_by_id[movie_id] for movie_id in public_ordered_ids]
    collaborative_support_items = [
        collaborative_items_by_id[movie_id]
        for movie_id in collaborative_support_ids
        if movie_id in collaborative_items_by_id
    ]
    excluded_items: list[dict] = []
    for entry_type, entry_value in ordered_all_entries:
        if entry_type == "invalid":
            excluded_items.append(invalid_items[entry_value])
            continue

        if entry_value in public_ids:
            continue
        if (
            entry_value in collaborative_support_id_set
            and not _has_public_catalogue_policy_exclusion(merged_items_by_id[entry_value])
        ):
            continue
        excluded_items.append(merged_items_by_id[entry_value])

    return {
        "public_items": public_rows_source,
        "collaborative_support_items": collaborative_support_items,
        "excluded_items": excluded_items,
        "public_ids": public_ids,
        "collaborative_support_ids": collaborative_support_id_set,
        "has_ratings_summary": has_ratings_summary,
        "ratings_summary_by_movie": ratings_summary_by_movie,
    }


def _movie_ids_in_order(items: list[dict]) -> list[int]:
    ordered_ids: list[int] = []
    seen_ids: set[int] = set()
    for item in items:
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


def _build_invalid_item_fingerprint(item: dict) -> tuple[str, str, str, str]:
    return (
        _string_or_empty(item.get("tmdbId")),
        _string_or_empty(item.get("imdbId")),
        _string_or_empty(item.get("title")),
        _string_or_empty(item.get("year")),
    )


def _is_technically_invalid_support_item(
    item: dict,
    *,
    ratings_summary_by_movie: dict[int, dict],
    has_ratings_summary: bool,
) -> bool:
    movie_id = _parse_int(item.get("movieId"))
    if movie_id is None:
        return True
    if _has_enrichment_error(item):
        return True
    if has_ratings_summary and not _has_filtered_ratings(movie_id, ratings_summary_by_movie):
        return True
    return False


def _build_base_movie_csv_row(
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
        "suitabilityCategory": _string_or_empty(item.get("suitabilityCategory")),
        "standDisplayScore": _string_or_empty(item.get("standDisplayScore")),
        "standDisplayReasons": _join_list_values(item.get("standDisplayReasons", [])),
    }


def _build_public_movie_csv_row(
    item: dict,
    *,
    ratings_summary_by_movie: dict[int, dict],
) -> dict:
    return _build_base_movie_csv_row(
        item,
        ratings_summary_by_movie=ratings_summary_by_movie,
    )


def _build_support_movie_csv_row(
    item: dict,
    *,
    ratings_summary_by_movie: dict[int, dict],
) -> dict:
    row = _build_base_movie_csv_row(
        item,
        ratings_summary_by_movie=ratings_summary_by_movie,
    )
    row.update(
        {
            "publicExclusionReasons": _join_list_values(
                item.get("publicExclusionReasons", [])
            ),
            "publicBlockedTerms": _join_list_values(item.get("publicBlockedTerms", [])),
            "suitabilityReasons": _join_list_values(item.get("suitabilityReasons", [])),
        }
    )
    return row


def _build_excluded_movie_csv_row(
    item: dict,
    *,
    ratings_summary_by_movie: dict[int, dict],
    public_ids: set[int],
    collaborative_support_ids: set[int],
    has_ratings_summary: bool,
) -> dict:
    row = _build_support_movie_csv_row(
        item,
        ratings_summary_by_movie=ratings_summary_by_movie,
    )
    exclusion_reasons = _build_exclusion_reasons(
        item,
        public_ids=public_ids,
        collaborative_support_ids=collaborative_support_ids,
        ratings_summary_by_movie=ratings_summary_by_movie,
        has_ratings_summary=has_ratings_summary,
    )
    row.update(
        {
            "exclusionCategory": _build_exclusion_category(exclusion_reasons),
            "exclusionReasons": _join_list_values(exclusion_reasons),
        }
    )
    return row


def _build_exclusion_reasons(
    item: dict,
    *,
    public_ids: set[int],
    collaborative_support_ids: set[int],
    ratings_summary_by_movie: dict[int, dict],
    has_ratings_summary: bool,
) -> list[str]:
    reasons: list[str] = []
    movie_id = _parse_int(item.get("movieId"))
    if movie_id is None:
        reasons.append("missing_or_invalid_movie_id")
    if _has_enrichment_error(item):
        reasons.append("enrichment_error")
    if (
        movie_id is not None
        and has_ratings_summary
        and not _has_filtered_ratings(movie_id, ratings_summary_by_movie)
    ):
        reasons.append("missing_filtered_ratings")
    if movie_id is None or (
        movie_id not in public_ids and movie_id not in collaborative_support_ids
    ):
        reasons.append("not_public_or_collaborative_support")

    return list(dict.fromkeys(reasons))


def _build_exclusion_category(exclusion_reasons: list[str]) -> str:
    if "missing_or_invalid_movie_id" in exclusion_reasons:
        return "missing_or_invalid_movie_id"
    if "enrichment_error" in exclusion_reasons:
        return "enrichment_error"
    if "missing_filtered_ratings" in exclusion_reasons:
        return "missing_filtered_ratings"
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


def _load_ratings_summary_by_movie() -> tuple[dict[int, dict], bool]:
    if not ML_32M_DEMO_RATINGS_BY_MOVIE_PATH.exists():
        return {}, False

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

    return summary_by_movie, True


def _build_manifest(
    *,
    public_movies_count: int,
    collaborative_support_movies_count: int,
    excluded_movies_count: int,
    collaborative_ratings_count: int,
    public_audience_policy: str,
    minimum_runtime_minutes: int,
) -> dict:
    return {
        "datasetName": "movies_recommender_offline_dataset",
        "schemaVersion": 1,
        "generatedAt": _utc_timestamp(),
        "sourceDataset": "MovieLens 32M",
        "metadataSource": "TMDB",
        "canonicalLanguage": "en-US",
        "displayLanguage": "es-ES",
        "publicAudiencePolicy": public_audience_policy,
        "publicCataloguePolicy": {
            "excludeDocumentaries": True,
            "minimumRuntimeMinutes": minimum_runtime_minutes,
        },
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
            "catalogMovies": "csv/catalog_movies.csv",
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
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_filtered_ratings(movie_id: int, ratings_summary_by_movie: dict[int, dict]) -> bool:
    summary = ratings_summary_by_movie.get(movie_id, {})
    filtered_rating_count = _parse_int(summary.get("filteredRatingCount"))
    return filtered_rating_count is not None and filtered_rating_count > 0


def _has_enrichment_error(item: dict) -> bool:
    if item.get("enrichmentError"):
        return True
    public_exclusion_reasons = {
        _normalize_reason(reason)
        for reason in item.get("publicExclusionReasons", [])
        if reason
    }
    return "enrichment_error" in public_exclusion_reasons


def _has_public_catalogue_policy_exclusion(item: dict) -> bool:
    return bool(
        {"documentary", "short_runtime"}
        & {
            _normalize_reason(reason)
            for reason in item.get("publicExclusionReasons", [])
            if reason
        }
    )


def _string_or_empty(value: object) -> str:
    if value in (None, ""):
        return ""
    return str(value)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
