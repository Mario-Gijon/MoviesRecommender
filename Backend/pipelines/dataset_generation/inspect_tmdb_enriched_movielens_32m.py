import argparse
import json
from collections import Counter, defaultdict
from statistics import mean

from app.project_paths.dataset_paths import (
    ML_32M_TMDB_ENRICHED_PATH,
    ML_32M_TMDB_INSPECTION_PATH,
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


def main() -> None:
    _parse_args()
    if not ML_32M_TMDB_ENRICHED_PATH.exists():
        raise RuntimeError(
            "TMDB-enriched MovieLens 32M file is missing. "
            "Run `python -m pipelines.dataset_generation.enrich_movielens_32m_with_tmdb` first."
        )

    items = json.loads(ML_32M_TMDB_ENRICHED_PATH.read_text(encoding="utf-8"))
    inspection = _build_inspection(items)

    ML_32M_TMDB_INSPECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_32M_TMDB_INSPECTION_PATH.write_text(
        json.dumps(inspection, indent=2),
        encoding="utf-8",
    )

    print(f"Total enriched items: {inspection['general']['totalItems']}")
    print(f"Failed enrichments: {len(inspection['failedEnrichments'])}")
    print(
        f"Poster coverage: {inspection['general']['itemsWithPosterPath']}/"
        f"{inspection['general']['totalItems']}"
    )
    print(
        f"Keyword coverage: {inspection['general']['itemsWithKeywords']}/"
        f"{inspection['general']['totalItems']}"
    )
    print(
        f"ES certification coverage: {inspection['general']['itemsWithEsCertification']}/"
        f"{inspection['general']['totalItems']}"
    )
    print(
        f"US certification coverage: {inspection['general']['itemsWithUsCertification']}/"
        f"{inspection['general']['totalItems']}"
    )
    print("Counts by demo suitability:")
    for key, value in inspection["demoSuitabilityCounts"].items():
        print(f"- {key}: {value}")
    print("Top 15 family-friendly candidates:")
    for item in inspection["familyFriendlyCandidates"][:15]:
        print(f"- {item['cleanTitle']} ({item['year']}) | score={item['candidateScore']}")
    print("Top 15 teen candidates:")
    for item in inspection["teenCandidates"][:15]:
        print(f"- {item['cleanTitle']} ({item['year']}) | score={item['candidateScore']}")
    print("Top 15 adult/sensitive candidates:")
    for item in inspection["adultOrSensitiveCandidates"][:15]:
        print(f"- {item['cleanTitle']} ({item['year']}) | score={item['candidateScore']}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect the TMDB-enriched MovieLens 32M candidate catalog.",
    )
    return parser.parse_args()


def _build_inspection(items: list[dict]) -> dict:
    general = _build_general_stats(items)
    movielens = _build_movielens_stats(items)
    tmdb = _build_tmdb_stats(items)
    distributions = _build_distributions(items)
    classified_items = [_classify_item(item) for item in items]
    suitability_counts = Counter(item["demoSuitability"] for item in classified_items)
    failed_enrichments = [
        {
            "movieId": item.get("movieId"),
            "cleanTitle": item.get("cleanTitle"),
            "year": item.get("year"),
            "tmdbId": item.get("tmdbId"),
            "enrichmentError": item.get("enrichmentError"),
        }
        for item in classified_items
        if item.get("enrichmentError")
    ]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in classified_items:
        grouped[item["demoSuitability"]].append(_build_ranked_item(item))

    grouped["family_friendly_candidate"].sort(
        key=lambda item: (
            -item["recencyScore"],
            -item["candidateScore"],
            -item["ratingCount"],
            -item["tmdbPopularity"],
            item["cleanTitle"],
        )
    )
    grouped["teen_candidate"].sort(
        key=lambda item: (
            -item["recencyScore"],
            -item["candidateScore"],
            -item["ratingCount"],
            -item["tmdbPopularity"],
            item["cleanTitle"],
        )
    )
    grouped["adult_or_sensitive"].sort(
        key=lambda item: (
            -item["candidateScore"],
            -item["ratingCount"],
            item["cleanTitle"],
        )
    )
    grouped["unknown"].sort(
        key=lambda item: (
            -item["candidateScore"],
            -item["ratingCount"],
            item["cleanTitle"],
        )
    )

    for key in grouped:
        grouped[key] = grouped[key][:50]

    return {
        "general": general,
        "movieLens": movielens,
        "tmdb": tmdb,
        "distributions": distributions,
        "failedEnrichments": failed_enrichments,
        "demoSuitabilityCounts": {
            "family_friendly_candidate": suitability_counts.get("family_friendly_candidate", 0),
            "teen_candidate": suitability_counts.get("teen_candidate", 0),
            "adult_or_sensitive": suitability_counts.get("adult_or_sensitive", 0),
            "unknown": suitability_counts.get("unknown", 0),
        },
        "familyFriendlyCandidates": grouped.get("family_friendly_candidate", []),
        "teenCandidates": grouped.get("teen_candidate", []),
        "adultOrSensitiveCandidates": grouped.get("adult_or_sensitive", []),
        "unknownSuitabilityCandidates": grouped.get("unknown", []),
    }


def _build_general_stats(items: list[dict]) -> dict:
    return {
        "totalItems": len(items),
        "itemsWithTmdbData": sum(1 for item in items if item.get("tmdb", {}).get("id") is not None),
        "itemsWithEnrichmentError": sum(1 for item in items if item.get("enrichmentError")),
        "itemsWithPosterPath": sum(1 for item in items if item.get("tmdb", {}).get("posterPath")),
        "itemsWithOverview": sum(1 for item in items if item.get("tmdb", {}).get("overview")),
        "itemsWithKeywords": sum(1 for item in items if item.get("tmdb", {}).get("keywords")),
        "itemsWithCertifications": sum(1 for item in items if item.get("tmdb", {}).get("certifications")),
        "itemsWithEsCertification": sum(
            1 for item in items if item.get("tmdb", {}).get("certifications", {}).get("ES")
        ),
        "itemsWithUsCertification": sum(
            1 for item in items if item.get("tmdb", {}).get("certifications", {}).get("US")
        ),
    }


def _build_movielens_stats(items: list[dict]) -> dict:
    rating_counts = [item["ratingCount"] for item in items]
    average_ratings = [item["averageRating"] for item in items]
    candidate_scores = [item["candidateScore"] for item in items]
    data_reliability_scores = [item["dataReliabilityScore"] for item in items]
    recency_scores = [item["recencyScore"] for item in items]
    return {
        "ratingCount": _numeric_summary(rating_counts),
        "averageRating": _numeric_summary(average_ratings),
        "candidateScore": _numeric_summary(candidate_scores),
        "dataReliabilityScore": _numeric_summary(data_reliability_scores),
        "recencyScore": _numeric_summary(recency_scores),
        "topByRatingCount": _top_items(items, key="ratingCount", limit=20),
        "topByCandidateScore": _top_items(items, key="candidateScore", limit=20),
        "topByRecencyScore": _top_items(items, key="recencyScore", limit=20),
    }


def _build_tmdb_stats(items: list[dict]) -> dict:
    with_popularity = [item for item in items if item.get("tmdb", {}).get("popularity") is not None]
    with_vote_count = [item for item in items if item.get("tmdb", {}).get("voteCount") is not None]
    with_vote_average = [
        item
        for item in items
        if item.get("tmdb", {}).get("voteAverage") is not None
        and (item.get("tmdb", {}).get("voteCount") or 0) >= 500
    ]
    return {
        "topByPopularity": _top_items(with_popularity, nested_key=("tmdb", "popularity"), limit=20),
        "topByVoteCount": _top_items(with_vote_count, nested_key=("tmdb", "voteCount"), limit=20),
        "topByVoteAverageMinimum500Votes": _top_items(
            with_vote_average,
            nested_key=("tmdb", "voteAverage"),
            limit=20,
        ),
    }


def _build_distributions(items: list[dict]) -> dict:
    genres = Counter()
    keywords = Counter()
    years = Counter()
    decades = Counter()
    us_certifications = Counter()
    es_certifications = Counter()
    runtime_buckets = Counter()

    for item in items:
        tmdb = item.get("tmdb", {})
        genres.update(tmdb.get("genres", []))
        keywords.update(tmdb.get("keywords", []))

        year = item.get("year")
        if year is not None:
            years[str(year)] += 1
            decades[f"{(year // 10) * 10}s"] += 1

        certifications = tmdb.get("certifications", {})
        if certifications.get("US"):
            us_certifications[certifications["US"]] += 1
        if certifications.get("ES"):
            es_certifications[certifications["ES"]] += 1

        runtime = tmdb.get("runtime")
        if isinstance(runtime, int):
            runtime_buckets[_runtime_bucket(runtime)] += 1

    return {
        "tmdbGenres": genres.most_common(),
        "tmdbKeywords": keywords.most_common(),
        "years": years.most_common(),
        "decades": decades.most_common(),
        "usCertifications": us_certifications.most_common(),
        "esCertifications": es_certifications.most_common(),
        "runtimeBuckets": runtime_buckets.most_common(),
    }


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

    item = dict(item)
    item["demoSuitability"] = suitability
    item["suitabilityReasons"] = reasons
    return item


def _build_ranked_item(item: dict) -> dict:
    tmdb = item.get("tmdb", {})
    certifications = tmdb.get("certifications", {})
    return {
        "movieId": item.get("movieId"),
        "cleanTitle": item.get("cleanTitle"),
        "year": item.get("year"),
        "ratingCount": item.get("ratingCount"),
        "averageRating": item.get("averageRating"),
        "candidateScore": item.get("candidateScore"),
        "dataReliabilityScore": item.get("dataReliabilityScore"),
        "recencyScore": item.get("recencyScore"),
        "tmdbPopularity": tmdb.get("popularity") or 0,
        "tmdbVoteAverage": tmdb.get("voteAverage"),
        "tmdbVoteCount": tmdb.get("voteCount"),
        "genres": tmdb.get("genres", []),
        "keywords": tmdb.get("keywords", [])[:10],
        "certifications": {
            key: certifications[key]
            for key in ("US", "ES", "GB")
            if certifications.get(key)
        },
        "posterPath": tmdb.get("posterPath"),
        "demoSuitability": item.get("demoSuitability"),
        "suitabilityReasons": item.get("suitabilityReasons", []),
    }


def _numeric_summary(values: list[float]) -> dict:
    if not values:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": min(values),
        "max": max(values),
        "avg": round(mean(values), 4),
    }


def _top_items(
    items: list[dict],
    *,
    key: str | None = None,
    nested_key: tuple[str, str] | None = None,
    limit: int,
) -> list[dict]:
    def sort_value(item: dict) -> float:
        if nested_key is not None:
            return item.get(nested_key[0], {}).get(nested_key[1]) or 0
        return item.get(key or "", 0) or 0

    selected = sorted(
        items,
        key=lambda item: (
            -sort_value(item),
            -item.get("ratingCount", 0),
            item.get("cleanTitle") or item.get("title", ""),
        ),
    )[:limit]
    return [
        {
            "movieId": item.get("movieId"),
            "title": item.get("cleanTitle") or item.get("title"),
            "ratingCount": item.get("ratingCount"),
            "averageRating": item.get("averageRating"),
            "candidateScore": item.get("candidateScore"),
            "dataReliabilityScore": item.get("dataReliabilityScore"),
            "recencyScore": item.get("recencyScore"),
            "tmdbPopularity": item.get("tmdb", {}).get("popularity"),
            "tmdbVoteAverage": item.get("tmdb", {}).get("voteAverage"),
            "tmdbVoteCount": item.get("tmdb", {}).get("voteCount"),
        }
        for item in selected
    ]


def _runtime_bucket(runtime: int) -> str:
    if runtime < 80:
        return "<80"
    if runtime < 100:
        return "80-99"
    if runtime < 120:
        return "100-119"
    if runtime < 150:
        return "120-149"
    return "150+"


if __name__ == "__main__":
    main()
