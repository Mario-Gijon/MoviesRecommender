from types import MappingProxyType
from typing import Mapping

from app.recommenders.collaborative.common.errors import (
    CollaborativeAlgorithmNotAvailableError,
    CollaborativeModelArtifactError,
    CollaborativeRecommendationError,
)
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationInput,
    CollaborativeRecommendedMovie,
    CollaborativeUserRating,
)
from app.recommenders.collaborative.service import recommend_collaborative_movies
from app.recommenders.content_based.constants import (
    MINIMUM_REQUIRED_NON_NEUTRAL_RATINGS,
    NEUTRAL_RATING,
)
from app.recommenders.content_based.models import (
    ContentRecommendationRequest,
    TemporaryMovieRating,
)
from app.recommenders.content_based.recommender import (
    ContentRecommendationDomainError,
    recommend_content_based_movies,
)
from app.recommenders.unified.models import (
    RecommendationAdapter,
    RecommendationServiceError,
    UnifiedRecommendationExplanation,
    UnifiedRecommendationRequest,
    UnifiedRecommendedMovie,
)


CONTENT_STRATEGY = "content"
COLLABORATIVE_STRATEGY = "collaborative"


class ContentTfidfAdapter:
    def validate(
        self,
        request: UnifiedRecommendationRequest,
    ) -> None:
        return None

    def recommend(
        self,
        request: UnifiedRecommendationRequest,
    ) -> list[UnifiedRecommendedMovie]:
        try:
            result = recommend_content_based_movies(
                ContentRecommendationRequest(
                    ratings=[
                        TemporaryMovieRating(
                            movieId=item.movie_id,
                            rating=item.rating,
                        )
                        for item in request.ratings
                    ],
                    limit=request.limit,
                )
            )
        except ContentRecommendationDomainError as exc:
            raise _translate_content_error(exc, request=request) from exc
        except RuntimeError as exc:
            raise RecommendationServiceError(
                code="model_unavailable",
                message="The selected recommendation model is currently unavailable.",
                status_code=503,
            ) from exc

        return [
            UnifiedRecommendedMovie(
                movie_id=item.movieId,
                score=float(item.recommendationScore),
                match_percentage=_percentage_from_unit_score(
                    item.recommendationScore
                ),
                explanation=UnifiedRecommendationExplanation(
                    summary=item.explanation.headline,
                    reasons=list(item.explanation.reasons),
                ),
            )
            for item in result.recommendations
        ]


class CollaborativeAdapter:
    def __init__(
        self,
        *,
        internal_algorithm_id: str,
        score_scale: str,
        requires_ratings: bool,
    ) -> None:
        self._internal_algorithm_id = internal_algorithm_id
        self._score_scale = score_scale
        self._requires_ratings = requires_ratings

    def validate(
        self,
        request: UnifiedRecommendationRequest,
    ) -> None:
        if self._requires_ratings and not request.ratings:
            raise RecommendationServiceError(
                code="insufficient_ratings",
                message="There are not enough ratings to run this recommender.",
                details={
                    "minimumRequired": 1,
                    "received": 0,
                },
            )

    def recommend(
        self,
        request: UnifiedRecommendationRequest,
    ) -> list[UnifiedRecommendedMovie]:
        try:
            result = recommend_collaborative_movies(
                CollaborativeRecommendationInput(
                    ratings=[
                        CollaborativeUserRating(
                            movie_id=item.movie_id,
                            rating=item.rating,
                        )
                        for item in request.ratings
                    ],
                    limit=request.limit,
                ),
                algorithm_id=self._internal_algorithm_id,
            )
        except CollaborativeRecommendationError as exc:
            raise _translate_collaborative_error(exc) from exc

        return [
            UnifiedRecommendedMovie(
                movie_id=item.movie_id,
                score=float(item.score),
                match_percentage=self._match_percentage(item),
                explanation=UnifiedRecommendationExplanation(
                    summary=item.explanation.headline,
                    reasons=list(item.explanation.reasons),
                ),
            )
            for item in result.recommendations
        ]

    def _match_percentage(self, item: CollaborativeRecommendedMovie) -> float:
        if item.algorithm_details.get("fallback"):
            return _percentage_from_five_star_score(item.score)
        if self._score_scale == "preference":
            preference = float(
                item.algorithm_details.get("normalizedPreference", item.score)
            )
            return round(_clamp((preference + 2.0) / 4.0) * 100.0, 2)
        return _percentage_from_five_star_score(item.score)


RECOMMENDER_REGISTRY: Mapping[
    tuple[str, str],
    RecommendationAdapter,
] = MappingProxyType(
    {
        (CONTENT_STRATEGY, "tfidf"): ContentTfidfAdapter(),
        (
            COLLABORATIVE_STRATEGY,
            "popularity",
        ): CollaborativeAdapter(
            internal_algorithm_id="popularity_baseline",
            score_scale="five_star",
            requires_ratings=False,
        ),
        (
            COLLABORATIVE_STRATEGY,
            "item_knn",
        ): CollaborativeAdapter(
            internal_algorithm_id="item_knn_cosine",
            score_scale="preference",
            requires_ratings=True,
        ),
        (
            COLLABORATIVE_STRATEGY,
            "user_knn",
        ): CollaborativeAdapter(
            internal_algorithm_id="user_knn_pearson_shrinkage",
            score_scale="five_star",
            requires_ratings=True,
        ),
        (
            COLLABORATIVE_STRATEGY,
            "biased",
        ): CollaborativeAdapter(
            internal_algorithm_id="biased_matrix_factorization",
            score_scale="five_star",
            requires_ratings=True,
        ),
    }
)

def _translate_content_error(
    error: ContentRecommendationDomainError,
    *,
    request: UnifiedRecommendationRequest,
) -> RecommendationServiceError:
    if error.code == "insufficient_non_neutral_ratings":
        received = sum(
            item.rating != NEUTRAL_RATING for item in request.ratings
        )
        return RecommendationServiceError(
            code="insufficient_ratings",
            message="There are not enough ratings to run this recommender.",
            details={
                "minimumRequired": MINIMUM_REQUIRED_NON_NEUTRAL_RATINGS,
                "received": received,
                "requirement": "nonNeutralRatings",
            },
        )
    if error.code == "no_recommendations_available":
        return RecommendationServiceError(
            code=error.code,
            message=error.message,
        )
    public_code = {
        "duplicate_rating_movie": "duplicate_movie_rating",
        "unknown_public_movie": "unknown_movie",
    }.get(error.code, error.code)
    return RecommendationServiceError(
        code=public_code,
        message=error.message,
    )


def _translate_collaborative_error(
    error: CollaborativeRecommendationError,
) -> RecommendationServiceError:
    if isinstance(
        error,
        (
            CollaborativeModelArtifactError,
            CollaborativeAlgorithmNotAvailableError,
        ),
    ):
        return RecommendationServiceError(
            code="model_unavailable",
            message="The selected recommendation model is currently unavailable.",
            status_code=503,
        )
    return RecommendationServiceError(
        code="invalid_recommendation_input",
        message="The recommendation input is invalid for the selected algorithm.",
        status_code=400,
    )


def _percentage_from_unit_score(score: float) -> float:
    return round(_clamp(float(score)) * 100.0, 2)


def _percentage_from_five_star_score(score: float) -> float:
    return round(_clamp(float(score) / 5.0) * 100.0, 2)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
