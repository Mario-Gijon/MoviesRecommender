from app.domain.catalog_heuristics.constants import (
    BOOST_SIGNAL_GENRES,
    FAMILY_POSITIVE_TERMS,
)


def compute_stand_display_score(item: dict) -> tuple[float, list[str]]:
    tmdb = item.get("tmdb", {})
    genres = set(tmdb.get("genres", []))
    keyword_set = {keyword.lower() for keyword in tmdb.get("keywords", [])}
    reasons: list[str] = []

    recency_score = float(item.get("recencyScore") or 0.0)
    data_reliability_score = float(item.get("dataReliabilityScore") or 0.0)
    candidate_score = float(item.get("candidateScore") or 0.0)
    tmdb_popularity_signal = min(float(tmdb.get("popularity") or 0.0) / 100.0, 1.0)

    genre_match_count = len(genres & BOOST_SIGNAL_GENRES)
    genre_appeal_signal = min(genre_match_count / 4.0, 1.0)
    keyword_appeal_signal = min(len(keyword_set & FAMILY_POSITIVE_TERMS) / 4.0, 1.0)

    penalty = 0.0
    if item.get("suitabilityCategory") == "adult_or_sensitive":
        penalty += 0.10
        reasons.append("adult_signal_penalty")

    if recency_score >= 0.85:
        reasons.append("recent_movie")
    if {"Animation", "Family", "Adventure", "Fantasy"} & genres:
        reasons.append("family_animation_or_adventure")
    elif item.get("suitabilityCategory") == "teen" and {"Action", "Science Fiction"} & genres:
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
