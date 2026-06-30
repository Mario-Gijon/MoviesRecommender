from __future__ import annotations

import re

from app.recommenders.collaborative.common.explanations.models import (
    EvidenceMovie,
    EvidenceProfile,
)


_WHITESPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCTUATION_RE = re.compile(r"\s+([,.;:!?])")
_REPEATED_PUNCTUATION_RE = re.compile(r"([,.;:!?]){2,}")


def format_spanish_list(
    values: list[str],
    *,
    max_items: int = 3,
) -> str:
    cleaned = [_clean_fragment(value) for value in values if _clean_fragment(value)]
    if not cleaned:
        return ""

    if max_items > 0:
        cleaned = cleaned[:max_items]

    if len(cleaned) == 1:
        return cleaned[0]

    if len(cleaned) == 2:
        return f"{cleaned[0]} y {cleaned[1]}"

    return f"{', '.join(cleaned[:-1])} y {cleaned[-1]}"


def format_evidence_movies(
    evidence_movies: list[EvidenceMovie] | None,
    *,
    max_items: int = 3,
) -> str:
    if not evidence_movies:
        return ""

    return format_spanish_list(
        [movie.title for movie in evidence_movies],
        max_items=max_items,
    )


def format_shared_movies(
    evidence_profiles: list[EvidenceProfile] | None,
    *,
    max_profiles: int = 2,
    max_movies: int = 3,
) -> str:
    if not evidence_profiles:
        return ""

    titles: list[str] = []
    for profile in evidence_profiles[:max_profiles]:
        for movie in profile.sharedMovies:
            if movie.title not in titles:
                titles.append(movie.title)

    return format_spanish_list(titles, max_items=max_movies)


def format_profiles(
    evidence_profiles: list[EvidenceProfile] | None,
    *,
    max_items: int = 2,
) -> str:
    if not evidence_profiles:
        return ""

    labels: list[str] = []
    for profile in evidence_profiles[:max_items]:
        value = profile.profileLabel or profile.groupSummary
        cleaned = _clean_fragment(value or "")
        if cleaned:
            labels.append(cleaned)

    return format_spanish_list(labels, max_items=max_items)


def cleanup_rendered_text(text: str) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", text).strip()
    cleaned = _SPACE_BEFORE_PUNCTUATION_RE.sub(r"\1", cleaned)
    cleaned = _REPEATED_PUNCTUATION_RE.sub(r"\1", cleaned)
    cleaned = cleaned.replace(" .", ".").replace(" ,", ",")
    return cleaned


def _clean_fragment(value: str) -> str:
    return cleanup_rendered_text(str(value)).strip(" ,.;:")
