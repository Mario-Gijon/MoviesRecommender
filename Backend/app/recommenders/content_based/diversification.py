from __future__ import annotations

from .constants import (
    DEFAULT_DIVERSIFIED_LIMIT,
    MAX_DIVERSIFIED_LIMIT,
    MAX_SCORING_LIMIT,
    MMR_CANDIDATE_POOL_SIZE,
    MMR_LAMBDA,
)
from .models import (
    ContentIndex,
    DiversifiedContentCandidate,
    ScoredContentCandidate,
    UserProfile,
)
from .scoring import rank_by_recommendation_score


def diversify_scored_candidates(
    content_index: ContentIndex,
    scored_candidates: list[ScoredContentCandidate],
    *,
    limit: int = DEFAULT_DIVERSIFIED_LIMIT,
    lambda_value: float = MMR_LAMBDA,
) -> list[DiversifiedContentCandidate]:
    _validate_limit(limit)
    _validate_lambda(lambda_value)

    if not scored_candidates:
        return []

    candidate_count = min(limit, len(scored_candidates))
    selected_candidates: list[DiversifiedContentCandidate] = []
    remaining_candidates = list(scored_candidates)

    first_candidate = remaining_candidates.pop(0)
    selected_candidates.append(
        _to_diversified_candidate(
            candidate=first_candidate,
            mmr_score=first_candidate.recommendationScore,
            max_similarity_to_selected=0.0,
        )
    )

    while remaining_candidates and len(selected_candidates) < candidate_count:
        best_choice: DiversifiedContentCandidate | None = None
        best_candidate_index = -1

        for candidate_index, candidate in enumerate(remaining_candidates):
            max_similarity = _max_similarity_to_selected(
                content_index=content_index,
                candidate=candidate,
                selected=selected_candidates,
            )
            mmr_score = (
                lambda_value * candidate.recommendationScore
                - (1.0 - lambda_value) * max_similarity
            )
            diversified_candidate = _to_diversified_candidate(
                candidate=candidate,
                mmr_score=mmr_score,
                max_similarity_to_selected=max_similarity,
            )
            if best_choice is None or _is_better_choice(diversified_candidate, best_choice):
                best_choice = diversified_candidate
                best_candidate_index = candidate_index

        if best_choice is None:
            break

        selected_candidates.append(best_choice)
        remaining_candidates.pop(best_candidate_index)

    return selected_candidates


def rank_diversified_recommendations(
    content_index: ContentIndex,
    user_profile: UserProfile,
    *,
    limit: int = DEFAULT_DIVERSIFIED_LIMIT,
    candidate_pool_size: int = MMR_CANDIDATE_POOL_SIZE,
    lambda_value: float = MMR_LAMBDA,
) -> list[DiversifiedContentCandidate]:
    _validate_limit(limit)
    _validate_lambda(lambda_value)
    _validate_candidate_pool_size(candidate_pool_size)

    scored_candidates = rank_by_recommendation_score(
        content_index=content_index,
        user_profile=user_profile,
        limit=candidate_pool_size,
    )
    return diversify_scored_candidates(
        content_index=content_index,
        scored_candidates=scored_candidates,
        limit=limit,
        lambda_value=lambda_value,
    )


def _max_similarity_to_selected(
    *,
    content_index: ContentIndex,
    candidate: ScoredContentCandidate,
    selected: list[DiversifiedContentCandidate],
) -> float:
    candidate_row = content_index.features.getrow(content_index.movieIdToRowIndex[candidate.movieId])
    max_similarity = 0.0

    for selected_candidate in selected:
        selected_row = content_index.features.getrow(
            content_index.movieIdToRowIndex[selected_candidate.movieId]
        )
        similarity = float(candidate_row.dot(selected_row.transpose()).toarray()[0][0])
        if similarity > max_similarity:
            max_similarity = similarity

    return max_similarity


def _to_diversified_candidate(
    *,
    candidate: ScoredContentCandidate,
    mmr_score: float,
    max_similarity_to_selected: float,
) -> DiversifiedContentCandidate:
    return DiversifiedContentCandidate(
        movieId=candidate.movieId,
        displayTitle=candidate.displayTitle,
        year=candidate.year,
        suitabilityCategory=candidate.suitabilityCategory,
        standDisplayScore=candidate.standDisplayScore,
        contentSimilarity=candidate.contentSimilarity,
        recommendationScore=candidate.recommendationScore,
        mmrScore=float(mmr_score),
        maxSimilarityToSelected=float(max_similarity_to_selected),
        genres=candidate.genres,
        matchedSignals=candidate.matchedSignals,
    )


def _is_better_choice(
    candidate: DiversifiedContentCandidate,
    current_best: DiversifiedContentCandidate,
) -> bool:
    return (
        -candidate.mmrScore,
        -candidate.recommendationScore,
        -candidate.contentSimilarity,
        -candidate.standDisplayScore,
        candidate.displayTitle.casefold(),
        candidate.movieId,
    ) < (
        -current_best.mmrScore,
        -current_best.recommendationScore,
        -current_best.contentSimilarity,
        -current_best.standDisplayScore,
        current_best.displayTitle.casefold(),
        current_best.movieId,
    )


def _validate_limit(limit: int) -> None:
    if limit < 1:
        raise RuntimeError("Diversified limit must be at least 1.")
    if limit > MAX_DIVERSIFIED_LIMIT:
        raise RuntimeError(f"Diversified limit must be at most {MAX_DIVERSIFIED_LIMIT}.")


def _validate_lambda(lambda_value: float) -> None:
    if lambda_value < 0.0 or lambda_value > 1.0:
        raise RuntimeError("MMR lambda must be between 0 and 1.")


def _validate_candidate_pool_size(candidate_pool_size: int) -> None:
    if candidate_pool_size < 1:
        raise RuntimeError("Candidate pool size must be at least 1.")
    if candidate_pool_size > MAX_SCORING_LIMIT:
        raise RuntimeError(
            f"Candidate pool size must be at most {MAX_SCORING_LIMIT}."
        )
