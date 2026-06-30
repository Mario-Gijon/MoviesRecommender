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


SHARED_EVIDENCE_POOL_LIMIT = 6
VISIBLE_SHARED_EVIDENCE_LIMIT = 3


@dataclass(frozen=True)
class UserKnnExplanationContribution:
    neighbor_user_id: int
    neighbor_rank: int
    contribution: float


@dataclass(frozen=True)
class UserKnnRenderedExplanation:
    response_explanation: CollaborativeRecommendationExplanation
    structured_explanation: CollaborativeExplanation


def build_user_knn_explanation(
    *,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_session_id: str | None,
    contributions: list[UserKnnExplanationContribution],
    shared_positive_movie_ids_by_neighbor_user_id: dict[int, list[int]],
) -> UserKnnRenderedExplanation:
    shared_movie_pool = _build_shared_movie_pool(
        contributions=contributions,
        shared_positive_movie_ids_by_neighbor_user_id=(
            shared_positive_movie_ids_by_neighbor_user_id
        ),
    )
    visible_shared_movies = _select_visible_shared_movies(
        candidate_movie_id=candidate_movie_id,
        rank=rank,
        variant_id=variant_id,
        template_session_id=template_session_id,
        shared_movie_pool=shared_movie_pool,
    )
    evidence_strength = _infer_evidence_strength(
        shared_movies=visible_shared_movies,
        contributions=contributions,
    )
    candidate_title = _resolve_public_movie_title(candidate_movie_id)

    structured_explanation = render_collaborative_explanation(
        explanation_type="user_knn_similar_profiles",
        algorithm_id="user_knn_pearson_shrinkage",
        variant_id=variant_id,
        movie_id=candidate_movie_id,
        rank=rank,
        shared_evidence_movies=visible_shared_movies,
        evidence_strength=evidence_strength,
        candidate_title=candidate_title,
        template_session_id=template_session_id,
        explanation_source="user_knn_neighbor_evidence",
        fidelity="high" if visible_shared_movies else "medium",
        limitations=(
            []
            if visible_shared_movies
            else ["No habia suficientes peliculas compartidas visibles para explicar la recomendacion con mas detalle."]
        ),
        debug={
            "fullEvidenceCandidateMovieIds": [
                movie.movieId for movie in shared_movie_pool
            ],
            "fullEvidenceCandidateMovieTitles": [
                movie.title for movie in shared_movie_pool
            ],
            "visibleEvidenceMovieIds": [
                movie.movieId for movie in visible_shared_movies
            ],
            "visibleEvidenceMovieTitles": [
                movie.title for movie in visible_shared_movies
            ],
            "explanationEvidenceStrength": evidence_strength,
            "evidenceSelectionMode": "shared_positive_movies_from_top_neighbors",
            "positiveNeighborContributionCount": sum(
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

    return UserKnnRenderedExplanation(
        response_explanation=response_explanation,
        structured_explanation=structured_explanation,
    )


def _build_shared_movie_pool(
    *,
    contributions: list[UserKnnExplanationContribution],
    shared_positive_movie_ids_by_neighbor_user_id: dict[int, list[int]],
) -> list[EvidenceMovie]:
    positive_contributions = sorted(
        [
            contribution
            for contribution in contributions
            if contribution.contribution > 0
        ],
        key=lambda contribution: (
            contribution.contribution,
            -contribution.neighbor_rank,
        ),
        reverse=True,
    )

    shared_movies: list[EvidenceMovie] = []
    seen_movie_ids: set[int] = set()

    for contribution in positive_contributions:
        shared_movie_ids = shared_positive_movie_ids_by_neighbor_user_id.get(
            contribution.neighbor_user_id,
            [],
        )
        for movie_id in shared_movie_ids:
            if movie_id in seen_movie_ids:
                continue

            title = _resolve_public_movie_title(movie_id)
            if not title:
                continue

            shared_movies.append(
                EvidenceMovie(
                    movieId=movie_id,
                    title=title,
                    role="shared_positive_movie",
                )
            )
            seen_movie_ids.add(movie_id)

            if len(shared_movies) >= SHARED_EVIDENCE_POOL_LIMIT:
                return shared_movies

    return shared_movies


def _select_visible_shared_movies(
    *,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_session_id: str | None,
    shared_movie_pool: list[EvidenceMovie],
) -> list[EvidenceMovie]:
    if len(shared_movie_pool) <= VISIBLE_SHARED_EVIDENCE_LIMIT:
        return list(shared_movie_pool)

    anchor_movie = shared_movie_pool[0]
    remaining_pool = shared_movie_pool[1:]
    ordered_remaining = sorted(
        remaining_pool,
        key=lambda movie: _stable_diversity_key(
            candidate_movie_id=candidate_movie_id,
            rank=rank,
            variant_id=variant_id,
            template_session_id=template_session_id,
            source_movie_id=movie.movieId,
            anchor_movie_id=anchor_movie.movieId,
        ),
    )
    selected_movies = [anchor_movie, *ordered_remaining[: VISIBLE_SHARED_EVIDENCE_LIMIT - 1]]
    selected_ids = {movie.movieId for movie in selected_movies}

    return [
        movie
        for movie in shared_movie_pool
        if movie.movieId in selected_ids
    ][:VISIBLE_SHARED_EVIDENCE_LIMIT]


def _infer_evidence_strength(
    *,
    shared_movies: list[EvidenceMovie],
    contributions: list[UserKnnExplanationContribution],
) -> str:
    if len(shared_movies) >= 2:
        return "strong"
    if len(shared_movies) == 1:
        return "medium"
    if any(contribution.contribution > 0 for contribution in contributions):
        return "medium"
    return "weak"


def _stable_diversity_key(
    *,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_session_id: str | None,
    source_movie_id: int,
    anchor_movie_id: int,
) -> str:
    payload = "|".join(
        [
            template_session_id or "",
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
