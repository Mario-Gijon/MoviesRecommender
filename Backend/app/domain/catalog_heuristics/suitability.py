from app.domain.catalog_heuristics.constants import (
    ADULT_ES,
    ADULT_US,
    BOOST_SIGNAL_GENRES,
    FAMILY_ES,
    FAMILY_POSITIVE_TERMS,
    FAMILY_US,
    SENSITIVE_GENRES,
    TEEN_ES,
    TEEN_US,
)
from app.domain.catalog_heuristics.text_signals import find_public_blocked_terms


def classify_item(item: dict) -> dict:
    tmdb = item.get("tmdb", {})
    genres = set(tmdb.get("genres", []))
    keywords = {keyword.lower() for keyword in tmdb.get("keywords", [])}
    certifications = tmdb.get("certifications", {})
    us_cert = certifications.get("US")
    es_cert = certifications.get("ES")
    public_blocked_terms = find_public_blocked_terms(item)
    reasons: list[str] = []

    sensitive_signal = bool(genres & SENSITIVE_GENRES)
    family_signal = bool(genres & BOOST_SIGNAL_GENRES) or bool(
        keywords & FAMILY_POSITIVE_TERMS
    )
    family_cert = us_cert in FAMILY_US or es_cert in FAMILY_ES

    if us_cert in ADULT_US or es_cert in ADULT_ES:
        reasons.append("Certification indicates adult/sensitive content")
        suitability = "adult_or_sensitive"
    elif us_cert in TEEN_US or es_cert in TEEN_ES:
        reasons.append("Certification indicates teen suitability")
        suitability = "teen"
    elif family_cert:
        reasons.append("Certification indicates family-friendly suitability")
        suitability = "family_friendly"
    else:
        suitability = "unknown"

    if sensitive_signal:
        reasons.append("Genre or keyword signal indicates sensitive themes")
        if family_cert:
            reasons.append("Warning: family certification conflicts with sensitive signal")
        elif suitability != "family_friendly":
            suitability = "adult_or_sensitive"

    if suitability == "unknown" and family_signal and not sensitive_signal:
        reasons.append("Family-oriented genres or keywords without sensitive signals")
        suitability = "family_friendly"
    elif suitability == "teen" and family_signal and not sensitive_signal:
        reasons.append("Family-oriented signals keep this near the teen/family boundary")
    elif suitability == "unknown":
        reasons.append("Missing or unclear certification and content signals")

    if public_blocked_terms:
        suitability = "adult_or_sensitive"
        reasons.append("Public blocked topic signal detected")

    analyzed = dict(item)
    analyzed["suitabilityCategory"] = suitability
    analyzed["publicBlockedTerms"] = public_blocked_terms
    analyzed["suitabilityReasons"] = reasons
    return analyzed
