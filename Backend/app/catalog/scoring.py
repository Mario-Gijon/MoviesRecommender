from app.catalog.certifications import (
    has_resolved_family_certification,
)
from app.catalog.constants import (
    STAND_CATEGORY_PENALTIES,
    STAND_DISPLAY_WEIGHTS,
    STAND_FAMILY_CONTEXT_ANCHOR_GENRES,
    STAND_FAMILY_CONTEXT_MIN_SUPPORT_MATCHES,
    STAND_FAMILY_CONTEXT_SENSITIVE_PENALTY_MULTIPLIER,
    STAND_FAMILY_CONTEXT_SUPPORT_GENRES,
    STAND_GENRE_APPEAL_SATURATION,
    STAND_GENRE_APPEAL_WEIGHTS,
    STAND_MAX_SENSITIVE_GENRE_PENALTY,
    STAND_POSITIVE_TERM_SATURATION,
    STAND_POSITIVE_TERM_WEIGHTS,
    STAND_SENSITIVE_GENRE_PENALTIES,
    STAND_SUITABILITY_WEIGHTS,
    STAND_TEEN_WITH_FAMILY_CERT_SUITABILITY_WEIGHT,
    STAND_TMDB_POPULARITY_SATURATION,
)


def _has_official_family_certification(item: dict) -> bool:
    certifications = item.get("tmdb", {}).get("certifications", {})
    return has_resolved_family_certification(certifications)


def _compute_suitability_signal(item: dict) -> float:
    category = item.get("suitabilityCategory")
    if category == "teen" and _has_official_family_certification(item):
        return float(STAND_TEEN_WITH_FAMILY_CERT_SUITABILITY_WEIGHT)
    return float(STAND_SUITABILITY_WEIGHTS.get(category, 0.0))


def _compute_genre_appeal_signal(genres: set[str]) -> float:
    matched_weight = sum(
        weight
        for genre, weight in STAND_GENRE_APPEAL_WEIGHTS.items()
        if genre in genres
    )
    return min(matched_weight / STAND_GENRE_APPEAL_SATURATION, 1.0)


def _compute_positive_terms_signal(item: dict, keyword_set: set[str]) -> float:
    positive_terms = set(keyword_set)
    positive_terms.update(
        str(tag).strip().lower() for tag in item.get("userTags", []) if str(tag).strip()
    )
    matched_weight = sum(
        weight
        for term, weight in STAND_POSITIVE_TERM_WEIGHTS.items()
        if term in positive_terms
    )
    return min(matched_weight / STAND_POSITIVE_TERM_SATURATION, 1.0)


def _compute_tmdb_popularity_signal(tmdb: dict) -> float:
    popularity = float(tmdb.get("popularity") or 0.0)
    return min(popularity / STAND_TMDB_POPULARITY_SATURATION, 1.0)


def _compute_recognition_signal(
    tmdb_popularity_signal: float, data_reliability_score: float
) -> float:
    signal = 0.60 * tmdb_popularity_signal + 0.40 * data_reliability_score
    return max(0.0, min(signal, 1.0))


def _has_family_display_context(genres: set[str]) -> bool:
    anchor_match = bool(genres & STAND_FAMILY_CONTEXT_ANCHOR_GENRES)
    support_match_count = len(genres & STAND_FAMILY_CONTEXT_SUPPORT_GENRES)
    return anchor_match and support_match_count >= STAND_FAMILY_CONTEXT_MIN_SUPPORT_MATCHES


def _compute_sensitive_genre_penalty(genres: set[str], item: dict) -> float:
    if item.get("suitabilityCategory") not in {"teen", "family_friendly"}:
        return 0.0

    penalty = sum(
        weight
        for genre, weight in STAND_SENSITIVE_GENRE_PENALTIES.items()
        if genre in genres
    )
    penalty = min(penalty, STAND_MAX_SENSITIVE_GENRE_PENALTY)
    if penalty > 0 and _has_family_display_context(genres):
        penalty *= STAND_FAMILY_CONTEXT_SENSITIVE_PENALTY_MULTIPLIER
    return penalty


def _compute_category_penalty(item: dict) -> float:
    return float(STAND_CATEGORY_PENALTIES.get(item.get("suitabilityCategory"), 0.0))


def _compute_stand_penalty(genres: set[str], item: dict) -> float:
    return _compute_category_penalty(item) + _compute_sensitive_genre_penalty(genres, item)


def compute_stand_display_score(item: dict) -> tuple[float, list[str]]:
    tmdb = item.get("tmdb", {})
    genres = set(tmdb.get("genres", []))
    keyword_set = {
        str(keyword).strip().lower()
        for keyword in tmdb.get("keywords", [])
        if str(keyword).strip()
    }
    reasons: list[str] = []

    suitability_signal = _compute_suitability_signal(item)
    genre_appeal_signal = _compute_genre_appeal_signal(genres)
    recency_score = float(item.get("recencyScore") or 0.0)
    data_reliability_score = float(item.get("dataReliabilityScore") or 0.0)
    tmdb_popularity_signal = _compute_tmdb_popularity_signal(tmdb)
    recognition_signal = _compute_recognition_signal(
        tmdb_popularity_signal, data_reliability_score
    )
    positive_terms_signal = _compute_positive_terms_signal(item, keyword_set)
    sensitive_genre_penalty = _compute_sensitive_genre_penalty(genres, item)
    category_penalty = _compute_category_penalty(item)
    penalty = _compute_stand_penalty(genres, item)

    if item.get("suitabilityCategory") == "teen" and _has_official_family_certification(item):
        reasons.append("stand_family_certified_teen_suitability")
    elif suitability_signal >= 1.0:
        reasons.append("stand_family_suitability")
    elif suitability_signal >= 0.70:
        reasons.append("stand_teen_suitability")

    if genre_appeal_signal >= 0.75:
        reasons.append("strong_stand_genre_appeal")
    elif genre_appeal_signal >= 0.40:
        reasons.append("moderate_stand_genre_appeal")

    if recognition_signal >= 0.70:
        reasons.append("strong_public_recognition")
    elif recognition_signal >= 0.45:
        reasons.append("moderate_public_recognition")

    if recency_score >= 0.85:
        reasons.append("recent_movie")
    if positive_terms_signal >= 0.50:
        reasons.append("positive_audience_terms")
    if data_reliability_score >= 0.70:
        reasons.append("strong_movielens_data")
    if sensitive_genre_penalty > 0:
        reasons.append("sensitive_genre_display_penalty")
        if _has_family_display_context(genres):
            reasons.append("family_context_softens_sensitive_penalty")
    if category_penalty > 0:
        reasons.append("category_display_penalty")

    score = (
        STAND_DISPLAY_WEIGHTS["suitability"] * suitability_signal
        + STAND_DISPLAY_WEIGHTS["genreAppeal"] * genre_appeal_signal
        + STAND_DISPLAY_WEIGHTS["recognition"] * recognition_signal
        + STAND_DISPLAY_WEIGHTS["recency"] * recency_score
        + STAND_DISPLAY_WEIGHTS["positiveTerms"] * positive_terms_signal
        + STAND_DISPLAY_WEIGHTS["dataReliability"] * data_reliability_score
        - penalty
    )
    return round(max(score, 0.0), 4), reasons
