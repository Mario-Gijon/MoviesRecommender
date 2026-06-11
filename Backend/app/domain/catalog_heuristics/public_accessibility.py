from app.domain.catalog_heuristics.constants import (
    PUBLIC_STAND_ACCESSIBILITY_PROTECTED_GENRES,
    PUBLIC_STAND_COMMON_ORIGINAL_LANGUAGES,
    PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_DISPLAY_SCORE,
    PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_RATING_COUNT,
    PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_TMDB_POPULARITY,
)


def has_low_stand_accessibility(item: dict) -> bool:
    tmdb = item.get("tmdb", {})
    original_language = item.get("originalLanguage") or tmdb.get("originalLanguage")
    rating_count = int(item.get("ratingCount") or 0)
    tmdb_popularity = float(tmdb.get("popularity") or item.get("tmdbPopularity") or 0.0)
    stand_display_score = float(item.get("standDisplayScore") or 0.0)
    genres = set(item.get("genres") or tmdb.get("genres", []))

    if not original_language or original_language in PUBLIC_STAND_COMMON_ORIGINAL_LANGUAGES:
        return False
    if rating_count >= PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_RATING_COUNT:
        return False
    if tmdb_popularity >= PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_TMDB_POPULARITY:
        return False
    if stand_display_score >= PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_DISPLAY_SCORE:
        return False
    if genres & PUBLIC_STAND_ACCESSIBILITY_PROTECTED_GENRES:
        return False
    return True
