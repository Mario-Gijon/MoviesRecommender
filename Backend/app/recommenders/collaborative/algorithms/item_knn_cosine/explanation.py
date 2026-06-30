from __future__ import annotations

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


def build_item_knn_explanation(
    *,
    candidate_movie_id: int,
    rank: int,
    variant_id: str,
    template_session_id: str | None,
    contributions: list[ItemKnnExplanationContribution],
) -> ItemKnnRenderedExplanation:
    evidence_movies = _select_evidence_movies(contributions)
    evidence_strength = _infer_evidence_strength(evidence_movies)
    candidate_title = _resolve_public_movie_title(candidate_movie_id)

    structured_explanation = render_collaborative_explanation(
        explanation_type="item_knn_similar_movies",
        algorithm_id="item_knn_cosine",
        variant_id=variant_id,
        movie_id=candidate_movie_id,
        rank=rank,
        evidence_movies=evidence_movies,
        evidence_strength=evidence_strength,
        candidate_title=candidate_title,
        template_session_id=template_session_id,
        explanation_source="item_knn_contribution_evidence",
        fidelity="high" if evidence_movies else "medium",
        limitations=(
            []
            if evidence_movies
            else ["Pocas pistas directas de peliculas concretas en esta recomendacion."]
        ),
        debug={
            "evidenceMovieIds": [movie.movieId for movie in evidence_movies],
            "evidenceMovieTitles": [movie.title for movie in evidence_movies],
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


def _select_evidence_movies(
    contributions: list[ItemKnnExplanationContribution],
) -> list[EvidenceMovie]:
    positive_contributions = sorted(
        [
            contribution
            for contribution in contributions
            if contribution.contribution > 0
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

        if len(evidence_movies) >= 3:
            break

    return evidence_movies


def _infer_evidence_strength(evidence_movies: list[EvidenceMovie]) -> str:
    if len(evidence_movies) >= 2:
        return "strong"
    if len(evidence_movies) == 1:
        return "medium"
    return "weak"


def _resolve_public_movie_title(movie_id: int) -> str | None:
    try:
        movie = catalog_repository.get_public_movie_by_id(movie_id)
    except RuntimeError:
        return None

    title = movie.get("displayTitle") or movie.get("title")
    if title is None:
        return None
    return str(title)
