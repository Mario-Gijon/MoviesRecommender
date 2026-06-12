from __future__ import annotations

from .constants import (
    CONTENT_RECOMMENDATION_SCORE_WEIGHTS,
    DEFAULT_SCORING_LIMIT,
    MAX_SCORING_LIMIT,
    MIN_CONTENT_SIMILARITY_FOR_SCORING,
)
from .schemas import ContentIndex, ScoredContentCandidate, UserProfile
from .similarity import rank_by_content_similarity


def rank_by_recommendation_score(
    content_index: ContentIndex,
    user_profile: UserProfile,
    *,
    limit: int = DEFAULT_SCORING_LIMIT,
) -> list[ScoredContentCandidate]:
    _validate_scoring_config()
    _validate_limit(limit)

    similarity_candidates = rank_by_content_similarity(
        content_index=content_index,
        user_profile=user_profile,
        limit=MAX_SCORING_LIMIT,
    )

    scored_candidates: list[ScoredContentCandidate] = []
    for candidate in similarity_candidates:
        content_similarity = max(candidate.contentSimilarity, 0.0)
        if content_similarity < MIN_CONTENT_SIMILARITY_FOR_SCORING:
            continue

        recommendation_score = (
            CONTENT_RECOMMENDATION_SCORE_WEIGHTS["contentSimilarity"] * content_similarity
            + CONTENT_RECOMMENDATION_SCORE_WEIGHTS["standDisplayScore"] * candidate.standDisplayScore
        )
        scored_candidates.append(
            ScoredContentCandidate(
                movieId=candidate.movieId,
                displayTitle=candidate.displayTitle,
                year=candidate.year,
                suitabilityCategory=candidate.suitabilityCategory,
                standDisplayScore=candidate.standDisplayScore,
                contentSimilarity=content_similarity,
                recommendationScore=float(recommendation_score),
                genres=candidate.genres,
                matchedSignals=candidate.matchedSignals,
            )
        )

    scored_candidates.sort(
        key=lambda candidate: (
            -candidate.recommendationScore,
            -candidate.contentSimilarity,
            -candidate.standDisplayScore,
            candidate.displayTitle.casefold(),
            candidate.movieId,
        )
    )
    return scored_candidates[:limit]


def _validate_scoring_config() -> None:
    total_weight = sum(CONTENT_RECOMMENDATION_SCORE_WEIGHTS.values())
    if abs(total_weight - 1.0) > 1e-9:
        raise RuntimeError(
            "Content recommendation score weights must sum to 1.0. "
            f"Current total: {total_weight}"
        )


def _validate_limit(limit: int) -> None:
    if limit < 1:
        raise RuntimeError("Scoring limit must be at least 1.")
    if limit > MAX_SCORING_LIMIT:
        raise RuntimeError(f"Scoring limit must be at most {MAX_SCORING_LIMIT}.")
