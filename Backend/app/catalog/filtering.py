from argparse import Namespace

from app.catalog.constants import PUBLIC_MIN_STAND_DISPLAY_SCORE
from app.catalog.public_accessibility import (
    has_low_stand_accessibility,
)

PUBLIC_EXCLUSION_REASON_LABELS = {
    "documentary": "Documental",
    "short_runtime": "Corto (< 60 min)",
}


def public_catalogue_policy_reasons(item: dict, *, public_min_runtime: int) -> list[str]:
    """Return public-only policy exclusions from already enriched TMDB metadata."""
    tmdb = item.get("tmdb", {})
    genres = tmdb.get("genres") or []
    if isinstance(genres, str):
        genres = genres.split("|")
    normalized_genres = {str(genre).strip().casefold() for genre in genres if genre}
    reasons: list[str] = []
    if "documentary" in normalized_genres:
        reasons.append("documentary")
    try:
        runtime = float(tmdb.get("runtime"))
    except (TypeError, ValueError):
        runtime = None
    if runtime is not None and runtime < public_min_runtime:
        reasons.append("short_runtime")
    return reasons


def build_public_exclusion_reasons(item: dict, *, args: Namespace) -> list[str]:
    reasons: list[str] = []
    tmdb = item.get("tmdb", {})
    rating_count = int(item.get("ratingCount") or 0)
    stand_display_score = item.get("standDisplayScore")
    year = item.get("year")
    public_blocked_terms = item.get("publicBlockedTerms", [])

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
    if public_blocked_terms:
        reasons.append("blocked_public_topic")
    if item.get("suitabilityCategory") == "adult_or_sensitive":
        reasons.append("adult_or_sensitive")
    if item.get("suitabilityCategory") == "unknown":
        reasons.append("unknown_suitability")
    if args.family_only and item.get("suitabilityCategory") == "teen":
        reasons.append("family_only_excludes_teen")
    reasons.extend(public_catalogue_policy_reasons(item, public_min_runtime=getattr(args, "public_min_runtime", 60)))
    if not reasons and has_low_stand_accessibility(item):
        reasons.append("low_stand_accessibility")
    if (
        not reasons
        and (
            stand_display_score is None
            or float(stand_display_score) < PUBLIC_MIN_STAND_DISPLAY_SCORE
        )
    ):
        reasons.append("low_stand_display_score")
    return reasons


def is_public_candidate(item: dict, *, args: Namespace) -> bool:
    tmdb = item.get("tmdb", {})
    stand_display_score = item.get("standDisplayScore")
    if item.get("enrichmentError"):
        return False
    if not tmdb.get("posterPath"):
        return False
    if int(item.get("ratingCount") or 0) < args.min_ratings:
        return False
    year = item.get("year")
    if year is None or year < args.public_min_year:
        return False
    if item.get("publicBlockedTerms"):
        return False
    if item.get("suitabilityCategory") in {"adult_or_sensitive", "unknown"}:
        return False
    if args.family_only and item.get("suitabilityCategory") != "family_friendly":
        return False
    if public_catalogue_policy_reasons(item, public_min_runtime=getattr(args, "public_min_runtime", 60)):
        return False
    if stand_display_score is None or float(stand_display_score) < PUBLIC_MIN_STAND_DISPLAY_SCORE:
        return False
    if has_low_stand_accessibility(item):
        return False
    return True


def is_collaborative_candidate(item: dict, *, args: Namespace) -> bool:
    if item.get("enrichmentError"):
        return False
    if int(item.get("ratingCount") or 0) < args.min_ratings:
        return False
    year = item.get("year")
    if year is None or year < args.collaborative_min_year:
        return False
    return True


def is_excluded_candidate(item: dict, *, args: Namespace) -> bool:
    return bool(item.get("publicExclusionReasons"))
