from app.domain.catalog_heuristics.constants import (
    ADULT_ES,
    ADULT_GENRES,
    ADULT_KEYWORDS,
    ADULT_US,
    FAMILY_ES,
    FAMILY_GENRES,
    FAMILY_KEYWORDS,
    FAMILY_US,
    TEEN_ES,
    TEEN_US,
)


def classify_item(item: dict) -> dict:
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
