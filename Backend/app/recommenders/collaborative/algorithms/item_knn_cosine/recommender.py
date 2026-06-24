import sqlite3
from dataclasses import dataclass, field

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.storage import (
    get_item_knn_cosine_variant_artifacts,
    load_item_knn_cosine_manifest,
)
from app.recommenders.collaborative.common.errors import CollaborativeModelArtifactError
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
    CollaborativeRecommendedMovie,
    CollaborativeRecommenderDetails,
)
from app.recommenders.collaborative.common.explanations.explanations import (
    CollaborativeExplanationContribution,
    build_collaborative_explanation,
)
from app.recommenders.collaborative.common.explanations.profile_style import (
    infer_collaborative_profile_style,
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

    def __init__(self, *, model_variant_id: str) -> None:
        self._model_variant_id = model_variant_id
        self._artifacts = get_item_knn_cosine_variant_artifacts(model_variant_id)
        self._manifest = self._load_manifest()

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult:
        self._validate_artifacts()

        rated_movie_ids = {rating.movie_id for rating in request.ratings}
        public_movie_ids = {
            int(movie["movieId"])
            for movie in catalog_repository.get_recommendation_candidates()
        }

        candidate_scores: dict[int, CandidateScore] = {}
        discarded_non_public_candidates = 0
        discarded_rated_candidates = 0
        ignored_neutral_ratings = 0
        missing_source_neighbor_rows = 0

        connection = sqlite3.connect(self._artifacts.neighbors_sqlite_path)
        try:
            for rating in request.ratings:
                rating_weight = _rating_to_weight(rating.rating)

                if rating_weight == 0:
                    ignored_neutral_ratings += 1
                    continue

                rows = connection.execute(
                    """
                    SELECT neighbor_movie_id, similarity, support
                    FROM item_neighbors
                    WHERE source_movie_id = ?
                    ORDER BY rank
                    """,
                    (rating.movie_id,),
                ).fetchall()

                if not rows:
                    missing_source_neighbor_rows += 1
                    continue

                for neighbor_movie_id, similarity, support in rows:
                    neighbor_movie_id = int(neighbor_movie_id)

                    if neighbor_movie_id in rated_movie_ids:
                        discarded_rated_candidates += 1
                        continue

                    if neighbor_movie_id not in public_movie_ids:
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
                            source_movie_id=rating.movie_id,
                            source_rating=rating.rating,
                            rating_weight=rating_weight,
                            similarity=similarity,
                            support=int(support),
                            contribution=contribution,
                        )
                    )
        finally:
            connection.close()

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

        return CollaborativeRecommendationResult(
            recommendations=recommendations,
            recommender_details=CollaborativeRecommenderDetails(
                algorithm_id=self.algorithm_id,
                algorithm_label=self.algorithm_label,
                is_personalized=True,
                is_explainable=True,
                status="ready",
                model_version=self._manifest.get("modelVersion"),
                details={
                    "modelVariant": self._model_variant_id,
                    "candidatePolicy": "public_movies_only",
                    "similarity": "cosine",
                    "ratingMode": "raw_explicit_ratings",
                    "profileStyle": profile_style,
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
            return load_item_knn_cosine_manifest(self._model_variant_id)
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


