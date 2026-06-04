import argparse
import json

from app.infrastructure.datasets.movielens_paths import (
    ML_32M_DEMO_CATALOG_PATH,
    ML_32M_TMDB_ENRICHED_PATH,
)


ADULT_GENRES = {"Horror", "Crime", "War", "Thriller"}
ADULT_KEYWORDS = {
    "murder",
    "serial killer",
    "drug",
    "prison",
    "violence",
    "holocaust",
    "nazi",
    "psychopath",
    "torture",
    "rape",
    "slavery",
    "revenge",
    "gore",
}
FAMILY_GENRES = {"Animation", "Family", "Adventure", "Fantasy", "Science Fiction", "Comedy"}
FAMILY_KEYWORDS = {
    "pixar",
    "disney",
    "magic",
    "friendship",
    "superhero",
    "superheroes",
    "school",
    "robot",
    "dinosaur",
    "time travel",
    "alien",
    "wizard",
    "family",
    "fantasy world",
}
FAMILY_US = {"G", "PG"}
FAMILY_ES = {"A", "Ai", "APTA", "7", "TP"}
TEEN_US = {"PG-13"}
TEEN_ES = {"12"}
ADULT_US = {"R", "NC-17"}
ADULT_ES = {"16", "18"}
BOOST_GENRES = {
    "Animation",
    "Family",
    "Adventure",
    "Fantasy",
    "Science Fiction",
    "Comedy",
    "Action",
}


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
            f"{item['demoSuitability']} | standDisplayScore={item['standDisplayScore']}"
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
        item for item in analyzed_items if _is_public_candidate(item, args=args)
    ]
    collaborative_candidates = [
        item for item in analyzed_items if _is_collaborative_candidate(item, args=args)
    ]
    excluded_candidates = [
        item for item in analyzed_items if _is_excluded_candidate(item, args=args)
    ]

    public_candidates.sort(key=_public_sort_key)
    collaborative_candidates.sort(key=_collaborative_sort_key)
    excluded_candidates.sort(key=_excluded_sort_key)

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
                if _is_public_candidate(item, args=args)
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
            1 for item in analyzed_items if item["demoSuitability"] == "family_friendly_candidate"
        ),
        "teenInputCount": sum(1 for item in analyzed_items if item["demoSuitability"] == "teen_candidate"),
        "adultOrSensitiveInputCount": sum(
            1 for item in analyzed_items if item["demoSuitability"] == "adult_or_sensitive"
        ),
        "unknownInputCount": sum(1 for item in analyzed_items if item["demoSuitability"] == "unknown"),
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
    analyzed = _classify_item(item)
    stand_display_score, stand_display_reasons = _compute_stand_display_score(analyzed)
    analyzed["standDisplayScore"] = stand_display_score
    analyzed["standDisplayReasons"] = stand_display_reasons
    analyzed["publicExclusionReasons"] = _build_public_exclusion_reasons(analyzed, args=args)
    return analyzed


def _classify_item(item: dict) -> dict:
    tmdb = item.get("tmdb", {})
    genres = set(tmdb.get("genres", []))
    keywords = {keyword.lower() for keyword in tmdb.get("keywords", [])}
    certifications = tmdb.get("certifications", {})
    us_cert = certifications.get("US")
    es_cert = certifications.get("ES")
    reasons: list[str] = []

    adult_signal = bool(genres & ADULT_GENRES) or bool(keywords & ADULT_KEYWORDS)
    family_signal = bool(genres & FAMILY_GENRES) or bool(keywords & FAMILY_KEYWORDS)
    family_cert = us_cert in FAMILY_US or es_cert in FAMILY_ES

    if us_cert in ADULT_US or es_cert in ADULT_ES:
        reasons.append("Certification indicates adult/sensitive content")
        suitability = "adult_or_sensitive"
    elif us_cert in TEEN_US or es_cert in TEEN_ES:
        reasons.append("Certification indicates teen suitability")
        suitability = "teen_candidate"
    elif family_cert:
        reasons.append("Certification indicates family-friendly suitability")
        suitability = "family_friendly_candidate"
    else:
        suitability = "unknown"

    if adult_signal:
        reasons.append("Genre or keyword signal indicates sensitive themes")
        if family_cert:
            reasons.append("Warning: family certification conflicts with adult signal")
        elif suitability != "family_friendly_candidate":
            suitability = "adult_or_sensitive"

    if suitability == "unknown" and family_signal and not adult_signal:
        reasons.append("Family-oriented genres or keywords without adult signals")
        suitability = "family_friendly_candidate"
    elif suitability == "teen_candidate" and family_signal and not adult_signal:
        reasons.append("Family-oriented signals keep this near the teen/family boundary")
    elif suitability == "unknown":
        reasons.append("Missing or unclear certification and content signals")

    analyzed = dict(item)
    analyzed["demoSuitability"] = suitability
    analyzed["suitabilityReasons"] = reasons
    return analyzed


def _compute_stand_display_score(item: dict) -> tuple[float, list[str]]:
    tmdb = item.get("tmdb", {})
    genres = set(tmdb.get("genres", []))
    keyword_set = {keyword.lower() for keyword in tmdb.get("keywords", [])}
    reasons: list[str] = []

    recency_score = float(item.get("recencyScore") or 0.0)
    data_reliability_score = float(item.get("dataReliabilityScore") or 0.0)
    candidate_score = float(item.get("candidateScore") or 0.0)
    tmdb_popularity_signal = min(float(tmdb.get("popularity") or 0.0) / 100.0, 1.0)

    genre_match_count = len(genres & BOOST_GENRES)
    genre_appeal_signal = min(genre_match_count / 4.0, 1.0)
    keyword_appeal_signal = min(len(keyword_set & FAMILY_KEYWORDS) / 4.0, 1.0)

    penalty = 0.0
    if item.get("demoSuitability") == "adult_or_sensitive":
        penalty += 0.10
        reasons.append("adult_signal_penalty")

    if recency_score >= 0.85:
        reasons.append("recent_movie")
    if {"Animation", "Family", "Adventure", "Fantasy"} & genres:
        reasons.append("family_animation_or_adventure")
    elif item.get("demoSuitability") == "teen_candidate" and {"Action", "Science Fiction"} & genres:
        reasons.append("teen_friendly_blockbuster")
    if tmdb_popularity_signal >= 0.6:
        reasons.append("strong_tmdb_popularity")
    if data_reliability_score >= 0.6 or candidate_score >= 0.6:
        reasons.append("strong_movielens_data")
    if keyword_appeal_signal > 0:
        reasons.append("audience_friendly_keywords")

    score = (
        0.30 * recency_score
        + 0.25 * genre_appeal_signal
        + 0.20 * tmdb_popularity_signal
        + 0.15 * data_reliability_score
        + 0.10 * keyword_appeal_signal
        - penalty
    )
    return round(max(score, 0.0), 4), reasons


def _build_public_exclusion_reasons(item: dict, *, args: argparse.Namespace) -> list[str]:
    reasons: list[str] = []
    tmdb = item.get("tmdb", {})
    rating_count = int(item.get("ratingCount") or 0)
    year = item.get("year")

    if item.get("enrichmentError"):
        reasons.append("enrichment_error")
    if not tmdb.get("posterPath"):
        reasons.append("missing_poster")
    if rating_count < args.min_ratings:
        reasons.append("below_min_ratings")
    if year is None:
        reasons.append("missing_year")
    else:
        if year < args.public_min_year:
            reasons.append("below_public_min_year")
    if item.get("demoSuitability") == "adult_or_sensitive":
        reasons.append("adult_or_sensitive")
    if item.get("demoSuitability") == "unknown":
        reasons.append("unknown_suitability")
    if args.family_only and item.get("demoSuitability") == "teen_candidate":
        reasons.append("family_only_excludes_teen")
    return reasons


def _is_public_candidate(item: dict, *, args: argparse.Namespace) -> bool:
    tmdb = item.get("tmdb", {})
    if item.get("enrichmentError"):
        return False
    if not tmdb.get("posterPath"):
        return False
    if int(item.get("ratingCount") or 0) < args.min_ratings:
        return False
    year = item.get("year")
    if year is None or year < args.public_min_year:
        return False
    if item.get("demoSuitability") in {"adult_or_sensitive", "unknown"}:
        return False
    if args.family_only and item.get("demoSuitability") != "family_friendly_candidate":
        return False
    return True


def _is_collaborative_candidate(item: dict, *, args: argparse.Namespace) -> bool:
    if item.get("enrichmentError"):
        return False
    if int(item.get("ratingCount") or 0) < args.min_ratings:
        return False
    year = item.get("year")
    if year is None or year < args.collaborative_min_year:
        return False
    return True


def _is_excluded_candidate(item: dict, *, args: argparse.Namespace) -> bool:
    return bool(item.get("publicExclusionReasons"))


def _public_priority(item: dict) -> int:
    if item.get("demoSuitability") == "family_friendly_candidate":
        return 0
    if item.get("demoSuitability") == "teen_candidate":
        return 1
    return 2


def _public_sort_key(item: dict) -> tuple:
    tmdb_popularity = float(item.get("tmdb", {}).get("popularity") or 0.0)
    return (
        -float(item.get("standDisplayScore") or 0.0),
        _public_priority(item),
        -float(item.get("recencyScore") or 0.0),
        -float(item.get("candidateScore") or 0.0),
        -float(item.get("dataReliabilityScore") or 0.0),
        -int(item.get("ratingCount") or 0),
        -tmdb_popularity,
        item.get("cleanTitle") or item.get("title") or "",
    )


def _collaborative_sort_key(item: dict) -> tuple:
    return (
        -int(item.get("ratingCount") or 0),
        -float(item.get("averageRating") or 0.0),
        -float(item.get("dataReliabilityScore") or 0.0),
        -float(item.get("candidateScore") or 0.0),
        item.get("cleanTitle") or item.get("title") or "",
    )


def _excluded_sort_key(item: dict) -> tuple:
    return (
        0 if item.get("demoSuitability") == "adult_or_sensitive" else 1,
        -float(item.get("candidateScore") or 0.0),
        -int(item.get("ratingCount") or 0),
        item.get("cleanTitle") or item.get("title") or "",
    )


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
        "demoSuitability": item.get("demoSuitability"),
        "suitabilityReasons": item.get("suitabilityReasons", []),
        "catalogRoles": catalog_roles,
        "publicExclusionReasons": item.get("publicExclusionReasons", []),
    }


if __name__ == "__main__":
    main()
