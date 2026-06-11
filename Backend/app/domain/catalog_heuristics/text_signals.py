import re
import unicodedata

from app.domain.catalog_heuristics.constants import PUBLIC_BLOCKED_TERMS

PUBLIC_BLOCKED_TERM_VARIANTS = {
    "dictator": {"dictators"},
    "drug": {"drugs"},
    "murder": {"murderer", "murderers", "murders"},
    "nazi": {"nazis"},
    "psychopath": {"psychopaths"},
    "rape": {"rapist", "rapists"},
    "suicide": {"suicidal"},
    "terrorism": {"terrorist", "terrorists"},
}


def normalize_text(value: object) -> str:
    if value is None:
        return ""

    normalized = str(value).lower()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _term_variants(term: str) -> set[str]:
    variants = {normalize_text(term)}
    variants.update(
        normalize_text(variant) for variant in PUBLIC_BLOCKED_TERM_VARIANTS.get(term, set())
    )
    return {variant for variant in variants if variant}


def _matches_normalized_term(term: str, searchable_values: list[str]) -> bool:
    pattern = rf"(^| ){re.escape(term)}( |$)"
    return any(re.search(pattern, value) for value in searchable_values)


def collect_public_blocked_searchable_text(item: dict) -> list[str]:
    tmdb = item.get("tmdb", {})
    text_values = [
        item.get("title"),
        item.get("cleanTitle"),
        item.get("displayTitle"),
        item.get("overview"),
        item.get("displayOverview"),
        tmdb.get("title"),
        tmdb.get("originalTitle"),
        tmdb.get("overview"),
        tmdb.get("displayTitle"),
        tmdb.get("displayOverview"),
    ]

    normalized_values: list[str] = []
    for value in text_values:
        normalized_value = normalize_text(value)
        if normalized_value:
            normalized_values.append(normalized_value)

    for value in tmdb.get("keywords", []):
        normalized_value = normalize_text(value)
        if normalized_value:
            normalized_values.append(normalized_value)

    for value in item.get("userTags", []):
        normalized_value = normalize_text(value)
        if normalized_value:
            normalized_values.append(normalized_value)

    return normalized_values


def find_public_blocked_terms(item: dict) -> list[str]:
    searchable_values = collect_public_blocked_searchable_text(item)
    matched_terms: list[str] = []

    for term in sorted(PUBLIC_BLOCKED_TERMS):
        normalized_variants = _term_variants(term)
        if not normalized_variants:
            continue

        if any(
            _matches_normalized_term(normalized_term, searchable_values)
            for normalized_term in normalized_variants
        ):
            matched_terms.append(term)

    return matched_terms


def has_public_blocked_topic(item: dict) -> bool:
    return bool(find_public_blocked_terms(item))
