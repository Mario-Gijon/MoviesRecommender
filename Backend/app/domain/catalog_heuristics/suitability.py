from app.domain.catalog_heuristics.certifications import (
    resolve_certification_suitability,
)
from app.domain.catalog_heuristics.constants import (
    BOOST_SIGNAL_GENRES,
    FAMILY_POSITIVE_TERMS,
    SENSITIVE_GENRES,
)
from app.domain.catalog_heuristics.text_signals import find_public_blocked_terms


def classify_item(item: dict) -> dict:
    tmdb = item.get("tmdb", {})
    genres = set(tmdb.get("genres", []))
    keywords = {keyword.lower() for keyword in tmdb.get("keywords", [])}
    certifications = tmdb.get("certifications", {})
    public_blocked_terms = find_public_blocked_terms(item)
    reasons: list[str] = []

    sensitive_signal = bool(genres & SENSITIVE_GENRES)
    family_signal = bool(genres & BOOST_SIGNAL_GENRES) or bool(
        keywords & FAMILY_POSITIVE_TERMS
    )
    suitability = resolve_certification_suitability(certifications)

    if suitability == "adult_or_sensitive":
        reasons.append("Certification indicates adult/sensitive content")
    elif suitability == "teen":
        reasons.append("Certification indicates teen suitability")
    elif suitability == "family_friendly":
        reasons.append("Certification indicates family-friendly suitability")

    if sensitive_signal:
        if suitability == "adult_or_sensitive":
            reasons.append("Sensitive genre signal also detected")
        elif suitability == "teen":
            reasons.append(
                "Sensitive genre signal detected, but official teen certification keeps teen suitability"
            )
        elif suitability == "family_friendly":
            reasons.append(
                "Family certification conflicts with sensitive genre signal; promoted to teen suitability"
            )
            suitability = "teen"
        else:
            reasons.append("Sensitive genre signal without clear certification")
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
