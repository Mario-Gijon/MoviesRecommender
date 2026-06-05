import argparse
import json

from app.domain.catalog_heuristics import (
    build_public_exclusion_reasons,
    classify_item,
    collaborative_sort_key,
    compute_stand_display_score,
    excluded_sort_key,
    is_collaborative_candidate,
    is_excluded_candidate,
    is_public_candidate,
    public_sort_key,
)
from app.infrastructure.datasets.movielens_paths import (
    ML_32M_DEMO_CATALOG_PATH,
    ML_32M_TMDB_ENRICHED_PATH,
)


def main() -> None:
    args = _parse_args()
    if not ML_32M_TMDB_ENRICHED_PATH.exists():
        raise RuntimeError(
            "TMDB-enriched MovieLens 32M file is missing. "
            "Run `python -m app.scripts.enrich_movielens_32m_with_tmdb` first."
        )

    items = json.loads(ML_32M_TMDB_ENRICHED_PATH.read_text(encoding="utf-8"))
    catalog = _build_catalog(items=items, args=args)

    ML_32M_DEMO_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_32M_DEMO_CATALOG_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    print(f"Total input items: {catalog['summary']['totalInputItems']}")
    print(f"Public eligible movies: {catalog['summary']['publicEligibleMovies']}")
    print(f"Public catalog movies written: {len(catalog['publicCatalog'])}")
    print(f"Public limit applied: {catalog['summary']['publicLimitApplied']}")
    print(f"Collaborative core written: {len(catalog['collaborativeCore'])}")
    print(f"Excluded/sensitive written: {len(catalog['excludedOrSensitive'])}")
    print("Top 25 public catalog movies:")
    for item in catalog["publicCatalog"][:25]:
        print(
            f"- {item['cleanTitle']} ({item['year']}) | "
            f"{item['suitabilityCategory']} | standDisplayScore={item['standDisplayScore']}"
        )
    print(f"Output path: {ML_32M_DEMO_CATALOG_PATH}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a processed demo catalog from TMDB-enriched MovieLens 32M candidates.",
    )
    parser.add_argument("--public-limit", type=int, default=None)
    parser.add_argument("--collaborative-core-limit", type=int, default=2000)
    parser.add_argument("--min-ratings", type=int, default=100)
    parser.add_argument("--public-min-year", type=int, default=2000)
    parser.add_argument("--collaborative-min-year", type=int, default=2000)
    parser.add_argument("--family-only", action="store_true")
    return parser.parse_args()


def _build_catalog(*, items: list[dict], args: argparse.Namespace) -> dict:
    analyzed_items = [_analyze_item(item, args=args) for item in items]

    public_candidates = [
        item for item in analyzed_items if is_public_candidate(item, args=args)
    ]
    collaborative_candidates = [
        item for item in analyzed_items if is_collaborative_candidate(item, args=args)
    ]
    excluded_candidates = [
        item for item in analyzed_items if is_excluded_candidate(item, args=args)
    ]

    public_candidates.sort(key=public_sort_key)
    collaborative_candidates.sort(key=collaborative_sort_key)
    excluded_candidates.sort(key=excluded_sort_key)

    public_catalog_candidates = _limit_items(public_candidates, args.public_limit)
    collaborative_core_candidates = _limit_items(
        collaborative_candidates,
        args.collaborative_core_limit,
    )

    collaborative_ids = {item.get("movieId") for item in collaborative_core_candidates}

    public_catalog = _dedupe_and_serialize(
        public_catalog_candidates,
        roles_by_movie_id={
            movie_id: ["public", "recommendable", "rateable"]
            + (["collaborative_core"] if movie_id in collaborative_ids else [])
            for movie_id in [item.get("movieId") for item in public_catalog_candidates]
        },
    )
    collaborative_core = _dedupe_and_serialize(
        collaborative_core_candidates,
        roles_by_movie_id={
            item.get("movieId"): (
                ["public", "recommendable", "rateable", "collaborative_core"]
                if is_public_candidate(item, args=args)
                else ["collaborative_core"]
            )
            for item in collaborative_core_candidates
        },
    )
    excluded_or_sensitive = _dedupe_and_serialize(
        excluded_candidates,
        roles_by_movie_id={
            item.get("movieId"): ["excluded_sensitive"] for item in excluded_candidates
        },
    )

    suitability_counts = {
        "familyFriendlyInputCount": sum(
            1 for item in analyzed_items if item["suitabilityCategory"] == "family_friendly"
        ),
        "teenInputCount": sum(1 for item in analyzed_items if item["suitabilityCategory"] == "teen"),
        "adultOrSensitiveInputCount": sum(
            1 for item in analyzed_items if item["suitabilityCategory"] == "adult_or_sensitive"
        ),
        "unknownInputCount": sum(1 for item in analyzed_items if item["suitabilityCategory"] == "unknown"),
    }

    return {
        "source": {
            "dataset": "ml-32m",
            "enrichment": "tmdb",
            "mode": "offline_processed_demo_catalog",
        },
        "summary": {
            "totalInputItems": len(items),
            "publicEligibleMovies": len(public_candidates),
            "publicCatalog": len(public_catalog),
            "publicLimitApplied": args.public_limit is not None,
            "collaborativeCore": len(collaborative_core),
            "excludedOrSensitive": len(excluded_or_sensitive),
            **suitability_counts,
        },
        "publicCatalog": public_catalog,
        "collaborativeCore": collaborative_core,
        "excludedOrSensitive": excluded_or_sensitive,
    }


def _analyze_item(item: dict, *, args: argparse.Namespace) -> dict:
    analyzed = classify_item(item)
    stand_display_score, stand_display_reasons = compute_stand_display_score(analyzed)
    analyzed["standDisplayScore"] = stand_display_score
    analyzed["standDisplayReasons"] = stand_display_reasons
    analyzed["publicExclusionReasons"] = build_public_exclusion_reasons(analyzed, args=args)
    return analyzed


def _dedupe_and_serialize(items: list[dict], *, roles_by_movie_id: dict[int, list[str]]) -> list[dict]:
    seen_movie_ids: set[int] = set()
    serialized_items: list[dict] = []

    for item in items:
        movie_id = item.get("movieId")
        if movie_id in seen_movie_ids:
            continue
        seen_movie_ids.add(movie_id)
        serialized_items.append(_serialize_item(item, catalog_roles=roles_by_movie_id.get(movie_id, [])))

    return serialized_items


def _limit_items(items: list[dict], limit: int | None) -> list[dict]:
    if limit is None:
        return items
    return items[:limit]


def _serialize_item(item: dict, *, catalog_roles: list[str]) -> dict:
    tmdb = item.get("tmdb", {})
    return {
        "movieId": item.get("movieId"),
        "tmdbId": item.get("tmdbId"),
        "imdbId": item.get("imdbId"),
        "title": item.get("title"),
        "cleanTitle": item.get("cleanTitle"),
        "displayTitle": (
            tmdb.get("displayTitle")
            or tmdb.get("title")
            or item.get("cleanTitle")
            or item.get("title")
        ),
        "year": item.get("year"),
        "overview": tmdb.get("overview"),
        "displayOverview": tmdb.get("displayOverview") or tmdb.get("overview"),
        "posterPath": tmdb.get("posterPath"),
        "backdropPath": tmdb.get("backdropPath"),
        "genres": tmdb.get("genres", []),
        "displayGenres": tmdb.get("displayGenres") or tmdb.get("genres", []),
        "keywords": tmdb.get("keywords", []),
        "userTags": item.get("userTags", []),
        "topCast": tmdb.get("topCast", []),
        "directors": tmdb.get("directors", []),
        "certifications": tmdb.get("certifications", {}),
        "runtime": tmdb.get("runtime"),
        "originalLanguage": tmdb.get("originalLanguage"),
        "tmdbPopularity": tmdb.get("popularity"),
        "tmdbVoteAverage": tmdb.get("voteAverage"),
        "tmdbVoteCount": tmdb.get("voteCount"),
        "ratingCount": item.get("ratingCount"),
        "averageRating": item.get("averageRating"),
        "candidateScore": item.get("candidateScore"),
        "dataReliabilityScore": item.get("dataReliabilityScore"),
        "recencyScore": item.get("recencyScore"),
        "standDisplayScore": item.get("standDisplayScore"),
        "standDisplayReasons": item.get("standDisplayReasons", []),
        "suitabilityCategory": item.get("suitabilityCategory"),
        "suitabilityReasons": item.get("suitabilityReasons", []),
        "publicBlockedTerms": item.get("publicBlockedTerms", []),
        "catalogRoles": catalog_roles,
        "publicExclusionReasons": item.get("publicExclusionReasons", []),
    }


if __name__ == "__main__":
    main()
