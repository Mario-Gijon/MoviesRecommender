import argparse
import json
from collections import Counter

from app.infrastructure.datasets.movielens_paths import (
    ML_LATEST_SMALL_DEMO_CATALOG_PATH,
    ML_LATEST_SMALL_TMDB_ENRICHED_PATH,
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
}
FAMILY_GENRES = {"Animation", "Family", "Adventure", "Fantasy", "Science Fiction", "Comedy"}
FAMILY_US = {"G", "PG"}
FAMILY_ES = {"A", "7", "TP"}
TEEN_US = {"PG-13"}
TEEN_ES = {"12"}
ADULT_US = {"R", "NC-17"}
ADULT_ES = {"16", "18"}
SUITABILITY_PRIORITY = {
    "family_friendly_candidate": 0,
    "teen_candidate": 1,
    "unknown": 2,
    "adult_or_sensitive": 3,
}
HIGH_APPEAL_GENRES = {"Animation", "Family", "Adventure", "Fantasy", "Comedy", "Science Fiction", "Action"}
CLASSIC_LOW_APPEAL_GENRES = {"Drama", "History", "Romance", "Mystery", "Crime", "Thriller"}
AUDIENCE_FRIENDLY_KEYWORDS = {
    "superhero",
    "superheroes",
    "magic",
    "friendship",
    "adventure",
    "space",
    "robot",
    "animation",
    "disney",
    "pixar",
    "wizard",
    "dinosaur",
    "time travel",
    "alien",
    "family",
    "school",
    "fantasy world",
}


def main() -> None:
    args = _parse_args()
    if not ML_LATEST_SMALL_TMDB_ENRICHED_PATH.exists():
        raise RuntimeError(
            "TMDB-enriched MovieLens file is missing. "
            "Run `python -m app.scripts.enrich_movielens_small_with_tmdb` first."
        )

    items = json.loads(ML_LATEST_SMALL_TMDB_ENRICHED_PATH.read_text(encoding="utf-8"))
    classified_items = [_classify_item(item) for item in items]
    suitability_counts = Counter(item["demoSuitability"] for item in classified_items)
    _annotate_stand_display_scores(classified_items)

    visible_candidates = []
    recommendation_candidates = []
    collaborative_candidates = []
    excluded_candidates = []

    for item in classified_items:
        public_result = _evaluate_public_eligibility(item, args)
        collaborative_result = _evaluate_collaborative_eligibility(item, args)

        roles: set[str] = set()

        if public_result["visible_eligible"]:
            roles.add("visible")
            visible_candidates.append(item)
        if public_result["recommendable_eligible"]:
            roles.add("recommendable")
            recommendation_candidates.append(item)
        if collaborative_result["eligible"]:
            roles.add("collaborative_core")
            collaborative_candidates.append(item)
        if public_result["excluded_sensitive"]:
            roles.add("excluded_sensitive")
            excluded_candidates.append(item)

        item["catalogRoles"] = sorted(roles)
        item["publicExclusionReasons"] = public_result["reasons"]

    visible_movies = _dedupe_and_limit(
        sorted(
            visible_candidates,
            key=lambda item: (
                SUITABILITY_PRIORITY[item["demoSuitability"]],
                -item["standDisplayScore"],
                -item["candidateScore"],
                -item["ratingCount"],
                -(item.get("tmdb", {}).get("popularity") or 0),
                item["cleanTitle"],
            ),
        ),
        args.visible_limit,
    )
    recommendation_pool = _dedupe_and_limit(
        sorted(
            recommendation_candidates,
            key=lambda item: (
                -item["candidateScore"],
                -item["standDisplayScore"],
                -item["ratingCount"],
                -(item.get("tmdb", {}).get("popularity") or 0),
                item["cleanTitle"],
            ),
        ),
        args.recommendation_limit,
    )
    collaborative_core = _dedupe_and_limit(
        sorted(
            collaborative_candidates,
            key=lambda item: (
                -item["ratingCount"],
                -item["averageRating"],
                -item["candidateScore"],
                item["cleanTitle"],
            ),
        ),
        args.collaborative_core_limit,
    )
    excluded_or_sensitive = _dedupe_and_limit(
        sorted(
            excluded_candidates,
            key=lambda item: (
                0 if item["demoSuitability"] == "adult_or_sensitive" else 1,
                -item["candidateScore"],
                -item["ratingCount"],
                item["cleanTitle"],
            ),
        ),
        None,
    )

    output = {
        "source": {
            "dataset": "ml-latest-small",
            "enrichment": "tmdb",
            "mode": "offline_processed_demo_catalog",
        },
        "summary": {
            "totalInputItems": len(classified_items),
            "visibleMovies": len(visible_movies),
            "recommendationPool": len(recommendation_pool),
            "collaborativeCore": len(collaborative_core),
            "excludedOrSensitive": len(excluded_or_sensitive),
            "familyFriendlyInputCount": suitability_counts.get("family_friendly_candidate", 0),
            "teenInputCount": suitability_counts.get("teen_candidate", 0),
            "adultOrSensitiveInputCount": suitability_counts.get("adult_or_sensitive", 0),
            "unknownInputCount": suitability_counts.get("unknown", 0),
        },
        "visibleMovies": [_serialize_catalog_item(item) for item in visible_movies],
        "recommendationPool": [_serialize_catalog_item(item) for item in recommendation_pool],
        "collaborativeCore": [_serialize_catalog_item(item) for item in collaborative_core],
        "excludedOrSensitive": [_serialize_catalog_item(item) for item in excluded_or_sensitive],
    }

    ML_LATEST_SMALL_DEMO_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_LATEST_SMALL_DEMO_CATALOG_PATH.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )

    print(f"Total input items: {output['summary']['totalInputItems']}")
    print(f"Visible movies written: {output['summary']['visibleMovies']}")
    print(f"Recommendation pool written: {output['summary']['recommendationPool']}")
    print(f"Collaborative core written: {output['summary']['collaborativeCore']}")
    print(f"Excluded/sensitive written: {output['summary']['excludedOrSensitive']}")
    print("Top 15 visible movie titles:")
    for item in output["visibleMovies"][:15]:
        print(f"- {item['cleanTitle']}")
    print("Top 15 recommendation pool titles:")
    for item in output["recommendationPool"][:15]:
        print(f"- {item['cleanTitle']}")
    print(f"Output path: {ML_LATEST_SMALL_DEMO_CATALOG_PATH}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a processed demo catalog from TMDB-enriched MovieLens latest-small candidates.",
    )
    parser.add_argument("--visible-limit", type=int, default=120)
    parser.add_argument("--recommendation-limit", type=int, default=220)
    parser.add_argument("--collaborative-core-limit", type=int, default=500)
    parser.add_argument("--min-ratings", type=int, default=20)
    parser.add_argument("--family-only", action="store_true")
    parser.add_argument("--min-year", type=int)
    parser.add_argument("--max-year", type=int)
    return parser.parse_args()


def _classify_item(item: dict) -> dict:
    tmdb = item.get("tmdb", {})
    genres = set(tmdb.get("genres", []))
    keywords = {keyword.lower() for keyword in tmdb.get("keywords", [])}
    certifications = tmdb.get("certifications", {})
    us_cert = certifications.get("US")
    es_cert = certifications.get("ES")
    reasons: list[str] = []

    adult_signal = bool(genres & ADULT_GENRES) or bool(keywords & ADULT_KEYWORDS)
    family_signal = bool(genres & FAMILY_GENRES)

    if us_cert in ADULT_US or es_cert in ADULT_ES:
        reasons.append("Certification indicates adult/sensitive content")
        suitability = "adult_or_sensitive"
    elif us_cert in TEEN_US or es_cert in TEEN_ES:
        reasons.append("Certification indicates teen suitability")
        suitability = "teen_candidate"
    elif us_cert in FAMILY_US or es_cert in FAMILY_ES:
        reasons.append("Certification indicates family-friendly suitability")
        suitability = "family_friendly_candidate"
    else:
        suitability = "unknown"

    if adult_signal:
        reasons.append("Genre or keyword signal indicates sensitive themes")
        if suitability != "family_friendly_candidate":
            suitability = "adult_or_sensitive"

    if suitability == "unknown" and family_signal and not adult_signal:
        reasons.append("Family-oriented genres without adult signals")
        suitability = "family_friendly_candidate"
    elif suitability == "teen_candidate" and family_signal and not adult_signal:
        reasons.append("Family-oriented genres keep this near the teen/family boundary")
    elif suitability == "unknown":
        reasons.append("Missing or unclear certification and content signals")

    result = dict(item)
    result["demoSuitability"] = suitability
    result["suitabilityReasons"] = reasons
    return result


def _evaluate_public_eligibility(item: dict, args: argparse.Namespace) -> dict:
    reasons: list[str] = []
    tmdb = item.get("tmdb", {})
    suitability = item["demoSuitability"]
    visible_eligible = True
    recommendable_eligible = True
    excluded_sensitive = False

    if item.get("enrichmentError"):
        reasons.append("enrichment_error")
        visible_eligible = False
        recommendable_eligible = False
        excluded_sensitive = True

    if not tmdb.get("posterPath"):
        reasons.append("missing_poster")
        visible_eligible = False
        recommendable_eligible = False
        excluded_sensitive = True

    if item.get("ratingCount", 0) < args.min_ratings:
        reasons.append("below_min_ratings")
        visible_eligible = False
        recommendable_eligible = False
        excluded_sensitive = True

    year = item.get("year")
    if args.min_year is not None and (year is None or year < args.min_year):
        reasons.append("below_min_year")
        visible_eligible = False
        recommendable_eligible = False
        excluded_sensitive = True
    if args.max_year is not None and (year is None or year > args.max_year):
        reasons.append("above_max_year")
        visible_eligible = False
        recommendable_eligible = False
        excluded_sensitive = True

    if suitability in {"adult_or_sensitive", "unknown"}:
        reasons.append("not_public_suitable")
        visible_eligible = False
        recommendable_eligible = False
        excluded_sensitive = True

    if args.family_only and suitability != "family_friendly_candidate":
        reasons.append("family_only_filter")
        visible_eligible = False
        recommendable_eligible = False
        if suitability != "family_friendly_candidate":
            excluded_sensitive = True

    return {
        "visible_eligible": visible_eligible,
        "recommendable_eligible": recommendable_eligible,
        "excluded_sensitive": excluded_sensitive,
        "reasons": reasons,
    }


def _evaluate_collaborative_eligibility(item: dict, args: argparse.Namespace) -> dict:
    eligible = True
    if item.get("ratingCount", 0) < args.min_ratings:
        eligible = False
    year = item.get("year")
    if args.min_year is not None and (year is None or year < args.min_year):
        eligible = False
    if args.max_year is not None and (year is None or year > args.max_year):
        eligible = False
    return {"eligible": eligible}


def _dedupe_and_limit(items: list[dict], limit: int | None) -> list[dict]:
    seen: set[int] = set()
    result = []
    for item in items:
        movie_id = item["movieId"]
        if movie_id in seen:
            continue
        seen.add(movie_id)
        result.append(item)
        if limit is not None and len(result) >= limit:
            break
    return result


def _annotate_stand_display_scores(items: list[dict]) -> None:
    max_tmdb_popularity = max(
        (item.get("tmdb", {}).get("popularity") or 0 for item in items),
        default=1,
    )
    max_rating_count = max((item.get("ratingCount") or 0 for item in items), default=1)

    for item in items:
        score, reasons = _compute_stand_display_score(
            item=item,
            max_tmdb_popularity=max_tmdb_popularity,
            max_rating_count=max_rating_count,
        )
        item["standDisplayScore"] = score
        item["standDisplayReasons"] = reasons


def _compute_stand_display_score(
    *,
    item: dict,
    max_tmdb_popularity: float,
    max_rating_count: int,
) -> tuple[float, list[str]]:
    tmdb = item.get("tmdb", {})
    genres = set(item.get("genres", []))
    keywords = {keyword.lower() for keyword in item.get("keywords", [])}
    year = item.get("year")
    reasons: list[str] = []

    recency_signal = _recency_signal(year)
    if recency_signal >= 0.85:
        reasons.append("recent_or_modern_movie")

    genre_appeal_signal = _genre_appeal_signal(genres)
    if genres & {"Animation", "Family", "Adventure"}:
        reasons.append("family_animation_or_adventure")

    popularity_signal = min((tmdb.get("popularity") or 0) / max_tmdb_popularity, 1.0) if max_tmdb_popularity else 0.0
    if popularity_signal >= 0.6:
        reasons.append("strong_tmdb_popularity")

    rating_count_signal = min((item.get("ratingCount") or 0) / max_rating_count, 1.0) if max_rating_count else 0.0
    data_reliability_signal = min(1.0, (item.get("candidateScore") or 0) * 0.7 + rating_count_signal * 0.3)
    if rating_count_signal >= 0.5:
        reasons.append("strong_movielens_rating_count")

    keyword_appeal_signal = _keyword_appeal_signal(keywords)
    if keyword_appeal_signal > 0:
        reasons.append("audience_friendly_keywords")

    classic_penalty = 0.0
    if year is not None and year < 1980 and not (genres & {"Adventure", "Family", "Science Fiction", "Fantasy"}):
        classic_penalty = 0.08
        reasons.append("classic_movie_penalty")

    score = (
        0.30 * recency_signal
        + 0.25 * genre_appeal_signal
        + 0.20 * popularity_signal
        + 0.15 * data_reliability_signal
        + 0.10 * keyword_appeal_signal
        - classic_penalty
    )
    return round(max(0.0, score), 4), reasons


def _recency_signal(year: int | None) -> float:
    if year is None:
        return 0.5
    if year >= 2000:
        return 1.0
    if year >= 1990:
        return 0.85
    if year >= 1980:
        return 0.65
    if year >= 1970:
        return 0.45
    return 0.25


def _genre_appeal_signal(genres: set[str]) -> float:
    if not genres:
        return 0.3
    score = 0.35
    if genres & HIGH_APPEAL_GENRES:
        score += 0.25
    if {"Animation", "Family"} & genres:
        score += 0.2
    if genres & {"Adventure", "Fantasy", "Science Fiction"}:
        score += 0.15
    if genres and genres.issubset(CLASSIC_LOW_APPEAL_GENRES):
        score -= 0.2
    return max(0.0, min(1.0, score))


def _keyword_appeal_signal(keywords: set[str]) -> float:
    if not keywords:
        return 0.0
    matches = 0
    for keyword in keywords:
        if keyword in AUDIENCE_FRIENDLY_KEYWORDS:
            matches += 1
    return min(1.0, matches / 3)


def _serialize_catalog_item(item: dict) -> dict:
    tmdb = item.get("tmdb", {})
    return {
        "movieId": item.get("movieId"),
        "tmdbId": item.get("tmdbId"),
        "imdbId": item.get("imdbId"),
        "title": item.get("title"),
        "cleanTitle": item.get("cleanTitle"),
        "year": item.get("year"),
        "overview": tmdb.get("overview"),
        "posterPath": tmdb.get("posterPath"),
        "backdropPath": tmdb.get("backdropPath"),
        "genres": tmdb.get("genres", []),
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
        "standDisplayScore": item.get("standDisplayScore"),
        "standDisplayReasons": item.get("standDisplayReasons", []),
        "demoSuitability": item.get("demoSuitability"),
        "suitabilityReasons": item.get("suitabilityReasons", []),
        "catalogRoles": item.get("catalogRoles", []),
    }


if __name__ == "__main__":
    main()
