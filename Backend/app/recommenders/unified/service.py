from app.catalog.catalog_repository import catalog_repository
from app.recommenders.unified.models import (
    RecommendationAdapter,
    RecommendationServiceError,
    UnifiedRecommendationRequest,
    UnifiedRecommendationResult,
)
from app.recommenders.unified.registry import RECOMMENDER_REGISTRY


MIN_LIMIT = 1
MAX_LIMIT = 50
MIN_RATING = 1
MAX_RATING = 5


def recommend_movies(
    request: UnifiedRecommendationRequest,
) -> UnifiedRecommendationResult:
    adapter = _resolve_adapter(
        strategy=request.strategy,
        algorithm=request.algorithm,
    )
    _validate_request(request)
    recommendations = adapter.recommend(request)
    return UnifiedRecommendationResult(
        strategy=request.strategy,
        algorithm=request.algorithm,
        recommendations=recommendations,
        limit=request.limit,
    )


def _resolve_adapter(*, strategy: str, algorithm: str) -> RecommendationAdapter:
    registered_strategies = {
        registered_strategy for registered_strategy, _ in RECOMMENDER_REGISTRY
    }
    registered_algorithms = {
        registered_algorithm for _, registered_algorithm in RECOMMENDER_REGISTRY
    }

    if strategy not in registered_strategies:
        raise RecommendationServiceError(
            code="unsupported_strategy",
            message=f"Recommendation strategy is not supported: {strategy}",
            details={"strategy": strategy},
        )
    if algorithm not in registered_algorithms:
        raise RecommendationServiceError(
            code="unsupported_algorithm",
            message=f"Recommendation algorithm is not supported: {algorithm}",
            details={"algorithm": algorithm},
        )

    adapter = RECOMMENDER_REGISTRY.get((strategy, algorithm))
    if adapter is None:
        raise RecommendationServiceError(
            code="unsupported_strategy_algorithm_combination",
            message="The selected strategy and algorithm combination is not supported.",
            details={
                "strategy": strategy,
                "algorithm": algorithm,
            },
        )
    return adapter


def _validate_request(request: UnifiedRecommendationRequest) -> None:
    if not request.ratings:
        raise RecommendationServiceError(
            code="empty_ratings",
            message="At least one rating is required.",
            details={"received": 0},
        )
    if type(request.limit) is not int or not MIN_LIMIT <= request.limit <= MAX_LIMIT:
        raise RecommendationServiceError(
            code="invalid_limit",
            message=f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}.",
            details={
                "minimum": MIN_LIMIT,
                "maximum": MAX_LIMIT,
                "received": request.limit,
            },
        )

    seen_movie_ids: set[int] = set()
    for item in request.ratings:
        if item.movie_id in seen_movie_ids:
            raise RecommendationServiceError(
                code="duplicate_movie_rating",
                message=f"Duplicate rating for movieId {item.movie_id}.",
                details={"movieId": item.movie_id},
            )
        if type(item.rating) is not int or not MIN_RATING <= item.rating <= MAX_RATING:
            raise RecommendationServiceError(
                code="invalid_rating_value",
                message=(
                    f"Rating for movieId {item.movie_id} must be an integer "
                    f"between {MIN_RATING} and {MAX_RATING}."
                ),
                details={
                    "movieId": item.movie_id,
                    "minimum": MIN_RATING,
                    "maximum": MAX_RATING,
                    "received": item.rating,
                },
            )
        try:
            catalog_repository.get_public_movie_by_id(item.movie_id)
        except RuntimeError as exc:
            raise RecommendationServiceError(
                code="unknown_movie",
                message=f"movieId {item.movie_id} is not in the public catalog.",
                details={"movieId": item.movie_id},
            ) from exc
        seen_movie_ids.add(item.movie_id)
