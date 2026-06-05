def _public_priority(item: dict) -> int:
    if item.get("demoSuitability") == "family_friendly_candidate":
        return 0
    if item.get("demoSuitability") == "teen_candidate":
        return 1
    return 2


def public_sort_key(item: dict) -> tuple:
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


def collaborative_sort_key(item: dict) -> tuple:
    return (
        -int(item.get("ratingCount") or 0),
        -float(item.get("averageRating") or 0.0),
        -float(item.get("dataReliabilityScore") or 0.0),
        -float(item.get("candidateScore") or 0.0),
        item.get("cleanTitle") or item.get("title") or "",
    )


def excluded_sort_key(item: dict) -> tuple:
    return (
        0 if item.get("demoSuitability") == "adult_or_sensitive" else 1,
        -float(item.get("candidateScore") or 0.0),
        -int(item.get("ratingCount") or 0),
        item.get("cleanTitle") or item.get("title") or "",
    )
