import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.storage import (
    get_item_knn_cosine_variant_artifacts,
    load_item_knn_cosine_manifest,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.recommender import (
    PopularityBaselineRecommender,
)
from app.recommenders.collaborative.common.errors import CollaborativeModelArtifactError
from app.recommenders.collaborative.common.explanations.explanations import (
    CollaborativeExplanationContribution,
    build_collaborative_explanation,
)
from app.recommenders.collaborative.common.explanations.profile_style import (
    infer_collaborative_profile_style,
)
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
    CollaborativeRecommendedMovie,
    CollaborativeRecommenderDetails,
)


@dataclass
class CandidateContribution:
    source_movie_id: int
    source_rating: int
    rating_weight: float
    similarity: float
    support: int
    contribution: float


@dataclass
class CandidateScore:
    movie_id: int
    weighted_sum: float = 0.0
    similarity_sum: float = 0.0
    contributions: list[CandidateContribution] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.weighted_sum


class ItemKnnCosineRecommender:
    algorithm_id = ALGORITHM_ID
    algorithm_label = ALGORITHM_LABEL

    def __init__(
        self,
        *,
        model_variant_id: str,
        artifact_root: Path | None = None,
        candidate_movie_ids: set[int] | None = None,
        candidate_policy: str = "public_movies_only",
    ) -> None:
        self._model_variant_id = model_variant_id
        self._artifact_root = artifact_root
        self._artifacts = get_item_knn_cosine_variant_artifacts(
            model_variant_id,
            artifact_root=artifact_root,
        )
        self._manifest = self._load_manifest()
        self._fallback_recommender = PopularityBaselineRecommender(
            artifact_root=artifact_root,
            candidate_movie_ids=candidate_movie_ids,
            candidate_policy=candidate_policy,
        )
        self._candidate_movie_ids = frozenset(
            candidate_movie_ids
            if candidate_movie_ids is not None
            else (
                int(movie["movieId"])
                for movie in catalog_repository.get_recommendation_candidates()
            )
        )
        self._candidate_policy = candidate_policy

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult:
        total_started_at = time.perf_counter()
        self._validate_artifacts()

        rated_movie_ids = {rating.movie_id for rating in request.ratings}
        candidate_movie_ids = self._candidate_movie_ids

        candidate_scores: dict[int, CandidateScore] = {}
        discarded_non_public_candidates = 0
        discarded_rated_candidates = 0
        ignored_neutral_ratings = 0
        missing_source_neighbor_rows = 0

        personalized_started_at = time.perf_counter()

        effective_ratings: list[tuple[int, int, float]] = []
        for rating in request.ratings:
            rating_weight = _rating_to_weight(rating.rating)

            if rating_weight == 0:
                ignored_neutral_ratings += 1
                continue

            effective_ratings.append(
                (
                    rating.movie_id,
                    rating.rating,
                    rating_weight,
                )
            )

        neighbor_rows_by_source = _load_neighbor_rows_by_source(
            sqlite_path=self._artifacts.neighbors_sqlite_path,
            source_movie_ids=list(dict.fromkeys(
                movie_id
                for movie_id, _, _ in effective_ratings
            )),
        )

        for source_movie_id, source_rating, rating_weight in effective_ratings:
            rows = neighbor_rows_by_source.get(source_movie_id, [])

            if not rows:
                missing_source_neighbor_rows += 1
                continue

            for neighbor_movie_id, similarity, support in rows:
                neighbor_movie_id = int(neighbor_movie_id)

                if neighbor_movie_id in rated_movie_ids:
                    discarded_rated_candidates += 1
                    continue

                if neighbor_movie_id not in candidate_movie_ids:
                    discarded_non_public_candidates += 1
                    continue

                similarity = float(similarity)
                contribution = similarity * rating_weight

                candidate_score = candidate_scores.setdefault(
                    neighbor_movie_id,
                    CandidateScore(movie_id=neighbor_movie_id),
                )
                candidate_score.weighted_sum += contribution
                candidate_score.similarity_sum += abs(similarity)
                candidate_score.contributions.append(
                    CandidateContribution(
                        source_movie_id=source_movie_id,
                        source_rating=source_rating,
                        rating_weight=rating_weight,
                        similarity=similarity,
                        support=int(support),
                        contribution=contribution,
                    )
                )

        ranked_candidates = sorted(
            [
                candidate
                for candidate in candidate_scores.values()
                if candidate.score > 0
            ],
            key=lambda candidate: candidate.score,
            reverse=True,
        )

        profile_style = infer_collaborative_profile_style(request.ratings)

        recommendations = [
            CollaborativeRecommendedMovie(
                movie_id=candidate.movie_id,
                rank=rank,
                score=round(candidate.score, 6),
                explanation=build_collaborative_explanation(
                    candidate_movie_id=candidate.movie_id,
                    rank=rank,
                    profile_style=profile_style,
                    template_session_id=request.template_session_id,
                    contributions=[
                        CollaborativeExplanationContribution(
                            source_movie_id=contribution.source_movie_id,
                            source_rating=contribution.source_rating,
                            rating_weight=contribution.rating_weight,
                            similarity=contribution.similarity,
                            support=contribution.support,
                            contribution=contribution.contribution,
                        )
                        for contribution in candidate.contributions
                    ],
                ),
                algorithm_details=_build_algorithm_details(candidate),
            )
            for rank, candidate in enumerate(
                ranked_candidates[: request.limit], start=1
            )
        ]

        personalized_runtime_ms = _elapsed_ms(personalized_started_at)
        personalized_recommendations = len(recommendations)

        fallback_runtime_ms = 0.0
        fallback_recommendations_added = 0

        if len(recommendations) < request.limit:
            fallback_started_at = time.perf_counter()
            excluded_movie_ids = {item.movie_id for item in recommendations}
            fallback_recommendations = self._fallback_recommender.recommend_fillers(
                rated_movie_ids=rated_movie_ids,
                excluded_movie_ids=excluded_movie_ids,
                limit=request.limit - len(recommendations),
                start_rank=len(recommendations) + 1,
                fallback=True,
            )
            fallback_runtime_ms = _elapsed_ms(fallback_started_at)
            fallback_recommendations_added = len(fallback_recommendations)
            recommendations.extend(fallback_recommendations)

        total_runtime_ms = _elapsed_ms(total_started_at)

        return CollaborativeRecommendationResult(
            recommendations=recommendations,
            recommender_details=CollaborativeRecommenderDetails(
                algorithm_id=self.algorithm_id,
                algorithm_label=self.algorithm_label,
                is_personalized=True,
                is_explainable=True,
                status="ready",
                model_version=self._manifest.get("modelVersion"),
                timing_ms=round(total_runtime_ms, 6),
                details={
                    "modelVariant": self._model_variant_id,
                    "candidatePolicy": self._candidate_policy,
                    "similarity": "cosine",
                    "ratingMode": "raw_explicit_ratings",
                    "neighborQueryMode": "batched_source_movie_ids",
                    "profileStyle": profile_style,
                    "personalizedRecommendations": personalized_recommendations,
                    "fallbackUsed": fallback_recommendations_added > 0,
                    "fallbackAlgorithm": (
                        PopularityBaselineRecommender.algorithm_id
                        if fallback_recommendations_added > 0
                        else None
                    ),
                    "fallbackRecommendationsAdded": fallback_recommendations_added,
                    "personalizedRuntimeMs": round(personalized_runtime_ms, 6),
                    "fallbackRuntimeMs": round(fallback_runtime_ms, 6),
                    "totalRuntimeMs": round(total_runtime_ms, 6),
                    "discardedNonPublicCandidates": discarded_non_public_candidates,
                    "discardedRatedCandidates": discarded_rated_candidates,
                    "ignoredNeutralRatings": ignored_neutral_ratings,
                    "missingSourceNeighborRows": missing_source_neighbor_rows,
                },
            ),
            limit=request.limit,
            template_session_id=request.template_session_id,
        )

    def _load_manifest(self) -> dict:
        try:
            return load_item_knn_cosine_manifest(
                self._model_variant_id,
                artifact_root=self._artifact_root,
            )
        except RuntimeError as exc:
            raise CollaborativeModelArtifactError(
                code="item_knn_cosine_manifest_missing",
                message=str(exc),
            ) from exc

    def _validate_artifacts(self) -> None:
        if not self._artifacts.neighbors_sqlite_path.exists():
            raise CollaborativeModelArtifactError(
                code="item_knn_cosine_sqlite_missing",
                message=(
                    "ItemKNN Cosine SQLite artifact is missing for variant "
                    f"{self._model_variant_id}: {self._artifacts.neighbors_sqlite_path}"
                ),
            )


def _load_neighbor_rows_by_source(
    *,
    sqlite_path: str,
    source_movie_ids: list[int],
) -> dict[int, list[tuple[int, float, int]]]:
    if not source_movie_ids:
        return {}

    placeholders = ", ".join("?" for _ in source_movie_ids)

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            f"""
            SELECT source_movie_id, neighbor_movie_id, similarity, support
            FROM item_neighbors
            WHERE source_movie_id IN ({placeholders})
            ORDER BY source_movie_id, rank
            """,
            source_movie_ids,
        ).fetchall()
    finally:
        connection.close()

    rows_by_source: dict[int, list[tuple[int, float, int]]] = {}

    for source_movie_id, neighbor_movie_id, similarity, support in rows:
        rows_by_source.setdefault(int(source_movie_id), []).append(
            (
                int(neighbor_movie_id),
                float(similarity),
                int(support),
            )
        )

    return rows_by_source


def _rating_to_weight(rating: int) -> float:
    return float(rating - 3)


def _build_algorithm_details(candidate: CandidateScore) -> dict:
    top_contributions = sorted(
        candidate.contributions,
        key=lambda contribution: abs(contribution.contribution),
        reverse=True,
    )[:5]

    return {
        "itemKnnScore": round(candidate.score, 6),
        "weightedSum": round(candidate.weighted_sum, 6),
        "similaritySum": round(candidate.similarity_sum, 6),
        "normalizedPreference": (
            round(
                candidate.weighted_sum / candidate.similarity_sum,
                6,
            )
            if candidate.similarity_sum != 0
            else 0.0
        ),
        "fallback": False,
        "contributingMovies": [
            {
                "movieId": contribution.source_movie_id,
                "rating": contribution.source_rating,
                "ratingWeight": contribution.rating_weight,
                "similarity": round(contribution.similarity, 6),
                "support": contribution.support,
                "contribution": round(contribution.contribution, 6),
            }
            for contribution in top_contributions
        ],
    }


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000
