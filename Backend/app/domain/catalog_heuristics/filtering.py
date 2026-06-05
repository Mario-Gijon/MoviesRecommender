from argparse import Namespace


def build_public_exclusion_reasons(item: dict, *, args: Namespace) -> list[str]:
    reasons: list[str] = []
    tmdb = item.get("tmdb", {})
    rating_count = int(item.get("ratingCount") or 0)
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
    return reasons


def is_public_candidate(item: dict, *, args: Namespace) -> bool:
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
    if item.get("publicBlockedTerms"):
        return False
    if item.get("suitabilityCategory") in {"adult_or_sensitive", "unknown"}:
        return False
    if args.family_only and item.get("suitabilityCategory") != "family_friendly":
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
