from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.common.explanations import (
    CollaborativeExplanation,
    EvidenceMovie,
    render_collaborative_explanation,
)
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationExplanation,
)


@dataclass(frozen=True)
class ItemKnnExplanationContribution:
    source_movie_id: int
    source_rating: int
    contribution: float


@dataclass(frozen=True)
class ItemKnnRenderedExplanation:
    response_explanation: CollaborativeRecommendationExplanation
    structured_explanation: CollaborativeExplanation


EVIDENCE_POOL_LIMIT = 6
VISIBLE_EVIDENCE_LIMIT = 3


def build_item_knn_explanation(
    *,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_seed: str | None,
    contributions: list[ItemKnnExplanationContribution],
    used_evidence_movie_counts: dict[int, int] | None = None,
) -> ItemKnnRenderedExplanation:
    full_evidence_pool = _build_evidence_pool(contributions)
    evidence_usage_counts_before = {
        movie.movieId: int(used_evidence_movie_counts.get(movie.movieId, 0))
        for movie in full_evidence_pool
    } if used_evidence_movie_counts is not None else {}
    visible_evidence_movies = _select_visible_evidence_movies(
        candidate_movie_id=candidate_movie_id,
        rank=rank,
        variant_id=variant_id,
        template_seed=template_seed,
        evidence_pool=full_evidence_pool,
        used_evidence_movie_counts=used_evidence_movie_counts,
    )
    evidence_strength = _infer_evidence_strength(visible_evidence_movies)
    candidate_title = _resolve_public_movie_title(candidate_movie_id)

    structured_explanation = render_collaborative_explanation(
        explanation_type="item_knn_similar_movies",
        algorithm_id="item_knn_cosine",
        variant_id=variant_id,
        movie_id=candidate_movie_id,
        rank=rank,
        evidence_movies=visible_evidence_movies,
        evidence_strength=evidence_strength,
        candidate_title=candidate_title,
        template_seed=template_seed,
        explanation_source="item_knn_contribution_evidence",
        fidelity="high" if visible_evidence_movies else "medium",
        limitations=(
            []
            if visible_evidence_movies
            else ["Pocas pistas directas de peliculas concretas en esta recomendacion."]
        ),
        debug={
            "evidenceMovieIds": [movie.movieId for movie in visible_evidence_movies],
            "evidenceMovieTitles": [movie.title for movie in visible_evidence_movies],
            "fullEvidenceCandidateMovieIds": [
                movie.movieId for movie in full_evidence_pool
            ],
            "fullEvidenceCandidateMovieTitles": [
                movie.title for movie in full_evidence_pool
            ],
            "visibleEvidenceMovieIds": [
                movie.movieId for movie in visible_evidence_movies
            ],
            "evidenceSelectionMode": "list_level_diverse_real_positive_evidence",
            "evidenceUsageCountsBefore": evidence_usage_counts_before,
            "positiveContributionCount": sum(
                1
                for contribution in contributions
                if contribution.contribution > 0
            ),
        },
    )

    response_explanation = CollaborativeRecommendationExplanation(
        headline=structured_explanation.explanationText,
        reasons=[],
        evidence=[movie.title for movie in structured_explanation.evidenceMovies],
    )

    return ItemKnnRenderedExplanation(
        response_explanation=response_explanation,
        structured_explanation=structured_explanation,
    )


def _build_evidence_pool(
    contributions: list[ItemKnnExplanationContribution],
) -> list[EvidenceMovie]:
    positive_contributions = sorted(
        [
            contribution
            for contribution in contributions
            if contribution.contribution > 0 and contribution.source_rating >= 4
        ],
        key=lambda contribution: contribution.contribution,
        reverse=True,
    )

    evidence_movies: list[EvidenceMovie] = []
    seen_movie_ids: set[int] = set()
    for contribution in positive_contributions:
        if contribution.source_movie_id in seen_movie_ids:
            continue

        title = _resolve_public_movie_title(contribution.source_movie_id)
        if not title:
            continue

        evidence_movies.append(
            EvidenceMovie(
                movieId=contribution.source_movie_id,
                title=title,
                userRating=contribution.source_rating,
                role="liked_source",
            )
        )
        seen_movie_ids.add(contribution.source_movie_id)

        if len(evidence_movies) >= EVIDENCE_POOL_LIMIT:
            break

    return evidence_movies


def _select_visible_evidence_movies(
    *,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_seed: str | None,
    evidence_pool: list[EvidenceMovie],
    used_evidence_movie_counts: dict[int, int] | None,
) -> list[EvidenceMovie]:
    if len(evidence_pool) <= VISIBLE_EVIDENCE_LIMIT:
        return list(evidence_pool)

    top_pool = evidence_pool[: min(3, len(evidence_pool))]
    anchor_movie = min(
        top_pool,
        key=lambda movie: _movie_selection_key(
            movie=movie,
            candidate_movie_id=candidate_movie_id,
            rank=rank,
            variant_id=variant_id,
            template_seed=template_seed,
            used_evidence_movie_counts=used_evidence_movie_counts,
            anchor_movie_id=movie.movieId,
        ),
    )

    remaining_pool = [
        movie
        for movie in evidence_pool
        if movie.movieId != anchor_movie.movieId
    ]
    remaining_needed = VISIBLE_EVIDENCE_LIMIT - 1
    ordered_remaining = sorted(
        remaining_pool,
        key=lambda movie: _movie_selection_key(
            movie=movie,
            candidate_movie_id=candidate_movie_id,
            rank=rank,
            variant_id=variant_id,
            template_seed=template_seed,
            used_evidence_movie_counts=used_evidence_movie_counts,
            anchor_movie_id=anchor_movie.movieId,
        ),
    )
    selected_movies = [anchor_movie, *ordered_remaining[:remaining_needed]]
    selected_movie_ids = {movie.movieId for movie in selected_movies}

    return [
        movie
        for movie in evidence_pool
        if movie.movieId in selected_movie_ids
    ][:VISIBLE_EVIDENCE_LIMIT]


def _movie_selection_key(
    *,
    movie: EvidenceMovie,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_seed: str | None,
    used_evidence_movie_counts: dict[int, int] | None,
    anchor_movie_id: int,
) -> tuple[int, str]:
    usage_count = 0
    if used_evidence_movie_counts is not None:
        usage_count = int(used_evidence_movie_counts.get(movie.movieId, 0))

    return (
        usage_count,
        _stable_diversity_key(
            candidate_movie_id=candidate_movie_id,
            rank=rank,
            variant_id=variant_id,
            template_seed=template_seed,
            source_movie_id=movie.movieId,
            anchor_movie_id=anchor_movie_id,
        ),
    )


def _infer_evidence_strength(evidence_movies: list[EvidenceMovie]) -> str:
    if len(evidence_movies) >= 2:
        return "strong"
    if len(evidence_movies) == 1:
        return "medium"
    return "weak"


def _stable_diversity_key(
    *,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_seed: str | None,
    source_movie_id: int,
    anchor_movie_id: int,
) -> str:
    payload = "|".join(
        [
            template_seed or "",
            str(candidate_movie_id),
            str(rank),
            variant_id,
            str(anchor_movie_id),
            str(source_movie_id),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_public_movie_title(movie_id: int) -> str | None:
    try:
        movie = catalog_repository.get_public_movie_by_id(movie_id)
    except RuntimeError:
        return None

    title = movie.get("displayTitle") or movie.get("title")
    if title is None:
        return None
    return str(title)
