import math
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.recommenders.collaborative.algorithms.popularity_baseline.recommender import (
    PopularityBaselineRecommender,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    UserKnnPearsonShrinkageRuntimeConfig,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.storage import (
    get_user_knn_pearson_shrinkage_artifacts,
    load_user_knn_pearson_shrinkage_manifest,
)
from app.recommenders.collaborative.common.errors import CollaborativeModelArtifactError
from app.recommenders.collaborative.common.explanations.profile_style import (
    infer_collaborative_profile_style,
)
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationExplanation,
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
    CollaborativeRecommendedMovie,
    CollaborativeRecommenderDetails,
)


@dataclass
class NeighborAccumulator:
    user_id: int
    numerator: float = 0.0
    active_squared_sum: float = 0.0
    neighbor_squared_sum: float = 0.0
    overlap: int = 0


@dataclass(frozen=True)
class NeighborSimilarity:
    user_id: int
    rank: int
    raw_similarity: float
    similarity: float
    overlap: int


@dataclass(frozen=True)
class UserKnnCandidateContribution:
    neighbor_rank: int
    similarity: float
    neighbor_rating: float
    neighbor_centered_rating: float
    contribution: float


@dataclass
class UserKnnCandidateScore:
    movie_id: int
    weighted_centered_sum: float = 0.0
    similarity_sum: float = 0.0
    neighbor_count: int = 0
    positive_neighbor_rating_count: int = 0
    contributions: list[UserKnnCandidateContribution] = field(default_factory=list)

    @property
    def predicted_centered_preference(self) -> float:
        if self.similarity_sum == 0:
            return 0.0

        return self.weighted_centered_sum / self.similarity_sum

    def predicted_rating(
        self,
        *,
        rating_center: float,
    ) -> float:
        return _clamp_rating(rating_center + self.predicted_centered_preference)

    def candidate_confidence(
        self,
        *,
        candidate_shrinkage: float,
    ) -> float:
        return self.neighbor_count / (self.neighbor_count + candidate_shrinkage)

    def regularized_score(
        self,
        *,
        rating_center: float,
        candidate_shrinkage: float,
    ) -> float:
        confidence = self.candidate_confidence(
            candidate_shrinkage=candidate_shrinkage,
        )

        return _clamp_rating(
            rating_center + self.predicted_centered_preference * confidence,
        )


class UserKnnPearsonShrinkageRecommender:
    algorithm_id = ALGORITHM_ID
    algorithm_label = ALGORITHM_LABEL

    def __init__(
        self,
        *,
        runtime_config: UserKnnPearsonShrinkageRuntimeConfig | None = None,
    ) -> None:
        self._runtime_config = runtime_config or UserKnnPearsonShrinkageRuntimeConfig()
        self._artifacts = get_user_knn_pearson_shrinkage_artifacts()
        self._manifest = self._load_manifest()
        self._fallback_recommender = PopularityBaselineRecommender()

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult:
        total_started_at = time.perf_counter()
        self._validate_artifacts()

        rated_movie_ids = {rating.movie_id for rating in request.ratings}
        profile_style = infer_collaborative_profile_style(request.ratings)

        effective_ratings = _build_effective_ratings(
            request=request,
            active_rating_center=self._runtime_config.active_rating_center,
        )
        ignored_neutral_ratings = len(request.ratings) - len(effective_ratings)

        personalized_started_at = time.perf_counter()

        neighbor_similarities: list[NeighborSimilarity] = []
        candidate_scores: dict[int, UserKnnCandidateScore] = {}
        overlap_rating_rows = 0
        public_candidate_rating_rows = 0
        candidate_users_considered = 0

        if effective_ratings:
            overlap_rows = _load_overlap_rows(
                sqlite_path=self._artifacts.ratings_sqlite_path,
                source_movie_ids=[
                    movie_id
                    for movie_id, _, _ in effective_ratings
                ],
            )
            overlap_rating_rows = len(overlap_rows)

            neighbor_accumulators = _build_neighbor_accumulators(
                overlap_rows=overlap_rows,
                effective_ratings=effective_ratings,
            )
            candidate_users_considered = len(neighbor_accumulators)

            neighbor_similarities = _select_neighbors(
                neighbor_accumulators=neighbor_accumulators,
                config=self._runtime_config,
            )

            if neighbor_similarities:
                public_candidate_rows = _load_public_candidate_rows(
                    sqlite_path=self._artifacts.ratings_sqlite_path,
                    neighbor_user_ids=[
                        neighbor.user_id
                        for neighbor in neighbor_similarities
                    ],
                )
                public_candidate_rating_rows = len(public_candidate_rows)

                candidate_scores = _build_candidate_scores(
                    public_candidate_rows=public_candidate_rows,
                    neighbor_similarities=neighbor_similarities,
                    rated_movie_ids=rated_movie_ids,
                )

        ranked_candidates = []
        filtered_low_support_candidates = 0
        filtered_low_score_candidates = 0

        for candidate in candidate_scores.values():
            if candidate.neighbor_count < self._runtime_config.min_candidate_neighbor_count:
                filtered_low_support_candidates += 1
                continue

            score = candidate.regularized_score(
                rating_center=self._runtime_config.active_rating_center,
                candidate_shrinkage=self._runtime_config.candidate_shrinkage,
            )

            if score <= self._runtime_config.min_prediction_score:
                filtered_low_score_candidates += 1
                continue

            ranked_candidates.append(candidate)

        ranked_candidates.sort(
            key=lambda candidate: (
                candidate.regularized_score(
                    rating_center=self._runtime_config.active_rating_center,
                    candidate_shrinkage=self._runtime_config.candidate_shrinkage,
                ),
                candidate.positive_neighbor_rating_count,
                candidate.neighbor_count,
                candidate.predicted_rating(
                    rating_center=self._runtime_config.active_rating_center,
                ),
            ),
            reverse=True,
        )

        recommendations = [
            CollaborativeRecommendedMovie(
                movie_id=candidate.movie_id,
                rank=rank,
                score=round(
                    candidate.regularized_score(
                        rating_center=self._runtime_config.active_rating_center,
                        candidate_shrinkage=self._runtime_config.candidate_shrinkage,
                    ),
                    6,
                ),
                explanation=_build_explanation(
                    candidate=candidate,
                    profile_style=profile_style,
                    config=self._runtime_config,
                ),
                algorithm_details=_build_algorithm_details(
                    candidate=candidate,
                    config=self._runtime_config,
                ),
            )
            for rank, candidate in enumerate(
                ranked_candidates[: request.limit],
                start=1,
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
                    "modelVariant": self._runtime_config.variant_id,
                    "candidatePolicy": "public_movies_only",
                    "neighborSearch": "on_demand_user_neighbors",
                    "similarity": "mean_centered_pearson_with_shrinkage",
                    "candidateScoring": "regularized_mean_centered_prediction",
                    "activeRatingCenter": self._runtime_config.active_rating_center,
                    "topNeighbors": self._runtime_config.top_neighbors,
                    "minOverlap": self._runtime_config.min_overlap,
                    "shrinkage": self._runtime_config.shrinkage,
                    "minCandidateNeighborCount": (
                        self._runtime_config.min_candidate_neighbor_count
                    ),
                    "candidateShrinkage": self._runtime_config.candidate_shrinkage,
                    "minPredictionScore": self._runtime_config.min_prediction_score,
                    "profileStyle": profile_style,
                    "candidateUsersConsidered": candidate_users_considered,
                    "selectedNeighbors": len(neighbor_similarities),
                    "overlapRatingRows": overlap_rating_rows,
                    "publicCandidateRatingRows": public_candidate_rating_rows,
                    "rawCandidateCount": len(candidate_scores),
                    "filteredLowSupportCandidates": filtered_low_support_candidates,
                    "filteredLowScoreCandidates": filtered_low_score_candidates,
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
                    "ignoredNeutralRatings": ignored_neutral_ratings,
                },
            ),
            limit=request.limit,
            template_session_id=request.template_session_id,
        )

    def _load_manifest(self) -> dict:
        try:
            return load_user_knn_pearson_shrinkage_manifest()
        except RuntimeError as exc:
            raise CollaborativeModelArtifactError(
                code="user_knn_pearson_shrinkage_manifest_missing",
                message=str(exc),
            ) from exc

    def _validate_artifacts(self) -> None:
        if not self._artifacts.ratings_sqlite_path.exists():
            raise CollaborativeModelArtifactError(
                code="user_knn_pearson_shrinkage_sqlite_missing",
                message=(
                    "UserKNN Pearson Shrinkage SQLite artifact is missing: "
                    f"{self._artifacts.ratings_sqlite_path}"
                ),
            )


def _build_effective_ratings(
    *,
    request: CollaborativeRecommendationRequest,
    active_rating_center: float,
) -> list[tuple[int, float, float]]:
    effective_ratings_by_movie_id: dict[int, tuple[int, float, float]] = {}

    for rating in request.ratings:
        active_centered_rating = float(rating.rating) - active_rating_center

        if active_centered_rating == 0:
            continue

        effective_ratings_by_movie_id[rating.movie_id] = (
            rating.movie_id,
            float(rating.rating),
            active_centered_rating,
        )

    return list(effective_ratings_by_movie_id.values())


def _load_overlap_rows(
    *,
    sqlite_path: Path,
    source_movie_ids: list[int],
) -> list[tuple[int, int, float]]:
    if not source_movie_ids:
        return []

    placeholders = ", ".join("?" for _ in source_movie_ids)

    connection = sqlite3.connect(sqlite_path)
    try:
        return connection.execute(
            f"""
            SELECT user_id, movie_id, centered_rating
            FROM user_ratings
            WHERE movie_id IN ({placeholders})
            """,
            source_movie_ids,
        ).fetchall()
    finally:
        connection.close()


def _build_neighbor_accumulators(
    *,
    overlap_rows: list[tuple[int, int, float]],
    effective_ratings: list[tuple[int, float, float]],
) -> dict[int, NeighborAccumulator]:
    active_centered_by_movie_id = {
        movie_id: active_centered_rating
        for movie_id, _, active_centered_rating in effective_ratings
    }

    neighbor_accumulators: dict[int, NeighborAccumulator] = {}

    for user_id, movie_id, neighbor_centered_rating in overlap_rows:
        active_centered_rating = active_centered_by_movie_id[int(movie_id)]

        accumulator = neighbor_accumulators.setdefault(
            int(user_id),
            NeighborAccumulator(user_id=int(user_id)),
        )
        accumulator.numerator += active_centered_rating * float(neighbor_centered_rating)
        accumulator.active_squared_sum += active_centered_rating * active_centered_rating
        accumulator.neighbor_squared_sum += (
            float(neighbor_centered_rating) * float(neighbor_centered_rating)
        )
        accumulator.overlap += 1

    return neighbor_accumulators


def _select_neighbors(
    *,
    neighbor_accumulators: dict[int, NeighborAccumulator],
    config: UserKnnPearsonShrinkageRuntimeConfig,
) -> list[NeighborSimilarity]:
    similarities: list[tuple[int, float, float, int]] = []

    for accumulator in neighbor_accumulators.values():
        if accumulator.overlap < config.min_overlap:
            continue

        denominator = math.sqrt(
            accumulator.active_squared_sum * accumulator.neighbor_squared_sum
        )
        if denominator == 0:
            continue

        raw_similarity = accumulator.numerator / denominator
        similarity = raw_similarity * (
            accumulator.overlap / (accumulator.overlap + config.shrinkage)
        )

        if similarity <= 0:
            continue

        similarities.append(
            (
                accumulator.user_id,
                raw_similarity,
                similarity,
                accumulator.overlap,
            )
        )

    similarities.sort(
        key=lambda item: (
            item[2],
            item[3],
            item[1],
            -item[0],
        ),
        reverse=True,
    )

    return [
        NeighborSimilarity(
            user_id=user_id,
            rank=rank,
            raw_similarity=raw_similarity,
            similarity=similarity,
            overlap=overlap,
        )
        for rank, (user_id, raw_similarity, similarity, overlap) in enumerate(
            similarities[: config.top_neighbors],
            start=1,
        )
    ]


def _load_public_candidate_rows(
    *,
    sqlite_path: Path,
    neighbor_user_ids: list[int],
) -> list[tuple[int, int, float, float]]:
    rows: list[tuple[int, int, float, float]] = []

    if not neighbor_user_ids:
        return rows

    connection = sqlite3.connect(sqlite_path)
    try:
        for chunk in _chunked(neighbor_user_ids, 900):
            placeholders = ", ".join("?" for _ in chunk)

            rows.extend(
                connection.execute(
                    f"""
                    SELECT user_id, movie_id, rating, centered_rating
                    FROM user_ratings
                    WHERE is_public_candidate = 1
                      AND user_id IN ({placeholders})
                    """,
                    chunk,
                ).fetchall()
            )
    finally:
        connection.close()

    return rows


def _build_candidate_scores(
    *,
    public_candidate_rows: list[tuple[int, int, float, float]],
    neighbor_similarities: list[NeighborSimilarity],
    rated_movie_ids: set[int],
) -> dict[int, UserKnnCandidateScore]:
    neighbor_by_user_id = {
        neighbor.user_id: neighbor
        for neighbor in neighbor_similarities
    }

    candidate_scores: dict[int, UserKnnCandidateScore] = {}

    for user_id, movie_id, rating, centered_rating in public_candidate_rows:
        movie_id = int(movie_id)

        if movie_id in rated_movie_ids:
            continue

        neighbor = neighbor_by_user_id[int(user_id)]
        similarity = neighbor.similarity
        centered_rating = float(centered_rating)
        contribution = similarity * centered_rating

        candidate_score = candidate_scores.setdefault(
            movie_id,
            UserKnnCandidateScore(movie_id=movie_id),
        )
        candidate_score.weighted_centered_sum += contribution
        candidate_score.similarity_sum += abs(similarity)
        candidate_score.neighbor_count += 1

        if float(rating) >= 4:
            candidate_score.positive_neighbor_rating_count += 1

        candidate_score.contributions.append(
            UserKnnCandidateContribution(
                neighbor_rank=neighbor.rank,
                similarity=similarity,
                neighbor_rating=float(rating),
                neighbor_centered_rating=centered_rating,
                contribution=contribution,
            )
        )

    return candidate_scores


def _build_explanation(
    *,
    candidate: UserKnnCandidateScore,
    profile_style: str,
    config: UserKnnPearsonShrinkageRuntimeConfig,
) -> CollaborativeRecommendationExplanation:
    if profile_style == "family":
        headline = "Usuarios con gustos parecidos también la valoraron bien."
    elif profile_style == "teen":
        headline = "Encaja con patrones de valoración de usuarios parecidos."
    else:
        headline = "La recomendamos por coincidencias con usuarios de perfil similar."

    return CollaborativeRecommendationExplanation(
        headline=headline,
        reasons=[
            (
                "Se ha calculado a partir de usuarios anónimos que coincidían "
                "con tus valoraciones en varias películas."
            ),
            (
                f"La predicción base es de "
                f"{candidate.predicted_rating(rating_center=config.active_rating_center):.2f} "
                "sobre 5 antes de regularizar por soporte."
            ),
            (
                f"El score usado para ordenar es "
                f"{candidate.regularized_score(rating_center=config.active_rating_center, candidate_shrinkage=config.candidate_shrinkage):.2f} "
                f"sobre 5, apoyado por {candidate.neighbor_count} valoraciones "
                "de vecinos seleccionados."
            ),
        ],
        evidence=[
            "UserKNN con ratings centrados por usuario, Pearson, shrinkage y regularización por soporte de candidata.",
        ],
    )


def _build_algorithm_details(
    *,
    candidate: UserKnnCandidateScore,
    config: UserKnnPearsonShrinkageRuntimeConfig,
) -> dict:
    top_contributions = sorted(
        candidate.contributions,
        key=lambda contribution: abs(contribution.contribution),
        reverse=True,
    )[:5]

    return {
        "userKnnScore": round(
            candidate.regularized_score(
                rating_center=config.active_rating_center,
                candidate_shrinkage=config.candidate_shrinkage,
            ),
            6,
        ),
        "predictedRatingRaw": round(
            candidate.predicted_rating(
                rating_center=config.active_rating_center,
            ),
            6,
        ),
        "predictedRatingRegularized": round(
            candidate.regularized_score(
                rating_center=config.active_rating_center,
                candidate_shrinkage=config.candidate_shrinkage,
            ),
            6,
        ),
        "predictedCenteredPreference": round(
            candidate.predicted_centered_preference,
            6,
        ),
        "candidateConfidence": round(
            candidate.candidate_confidence(
                candidate_shrinkage=config.candidate_shrinkage,
            ),
            6,
        ),
        "weightedCenteredSum": round(candidate.weighted_centered_sum, 6),
        "similaritySum": round(candidate.similarity_sum, 6),
        "neighborCount": candidate.neighbor_count,
        "positiveNeighborRatingCount": candidate.positive_neighbor_rating_count,
        "fallback": False,
        "neighborContributions": [
            {
                "neighborRank": contribution.neighbor_rank,
                "similarity": round(contribution.similarity, 6),
                "neighborRating": contribution.neighbor_rating,
                "neighborCenteredRating": round(
                    contribution.neighbor_centered_rating,
                    6,
                ),
                "contribution": round(contribution.contribution, 6),
            }
            for contribution in top_contributions
        ],
    }


def _chunked(
    values: list[int],
    size: int,
) -> list[list[int]]:
    return [
        values[index : index + size]
        for index in range(0, len(values), size)
    ]


def _clamp_rating(value: float) -> float:
    return max(0.5, min(5.0, value))


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000