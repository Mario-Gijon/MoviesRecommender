from app.catalog.constants import (
    ADULT_ES,
    ADULT_US,
    FAMILY_ES,
    FAMILY_US,
    TEEN_ES,
    TEEN_US,
)


def resolve_certification_suitability(certifications: dict) -> str:
    us_cert = certifications.get("US")
    es_cert = certifications.get("ES")

    if us_cert in ADULT_US or es_cert in ADULT_ES:
        return "adult_or_sensitive"
    if es_cert in TEEN_ES:
        return "teen"
    if es_cert in FAMILY_ES:
        return "family_friendly"
    if us_cert in TEEN_US:
        return "teen"
    if us_cert in FAMILY_US:
        return "family_friendly"
    return "unknown"


def has_resolved_family_certification(certifications: dict) -> bool:
    return resolve_certification_suitability(certifications) == "family_friendly"
