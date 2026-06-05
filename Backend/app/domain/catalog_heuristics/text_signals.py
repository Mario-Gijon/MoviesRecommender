import re

from app.domain.catalog_heuristics.constants import PUBLIC_BLOCKED_TERMS


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    normalized = str(value).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


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
        normalized_term = normalize_text(term)
        if not normalized_term:
            continue

        if " " in normalized_term:
            if any(normalized_term in value for value in searchable_values):
                matched_terms.append(term)
            continue

        pattern = rf"(^| ){re.escape(normalized_term)}( |$)"
        if any(re.search(pattern, value) for value in searchable_values):
            matched_terms.append(term)

    return matched_terms


def has_public_blocked_topic(item: dict) -> bool:
    return bool(find_public_blocked_terms(item))
