import logging

from fastapi import APIRouter

from app.api.recommendation_errors import (
    RecommendationHttpError,
    resolve_request_id,
)
from app.catalog.catalog_repository import catalog_repository
from app.recommenders.unified.models import (
    RecommendationRating,
    RecommendationServiceError,
    UnifiedRecommendationRequest,
    UnifiedRecommendationResult,
)
from app.recommenders.unified.service import recommend_movies
from app.schemas.catalog_schemas import PublicMovieRecord
from app.schemas.error_schemas import ErrorResponse
from app.schemas.recommendation_schemas import (
    RecommendationExplanation,
    RecommendationItemResponse,
    RecommendationMeta,
    RecommendationRequest,
    RecommendationResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(tags=["recommendations"])

CANONICAL_ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    responses=CANONICAL_ERROR_RESPONSES,
)
def create_recommendations(
    payload: RecommendationRequest,
) -> RecommendationResponse:
    request_id = resolve_request_id(payload.requestId)
    request = UnifiedRecommendationRequest(
        strategy=payload.strategy,
        algorithm=payload.algorithm,
        ratings=[
            RecommendationRating(
                movie_id=item.movieId,
                rating=item.rating,
            )
            for item in payload.ratings
        ],
        limit=payload.limit,
    )
    return _execute_recommendation(
        request=request,
        request_id=request_id,
    )


def _execute_recommendation(
    *,
    request: UnifiedRecommendationRequest,
    request_id: str,
) -> RecommendationResponse:
    logger.info(
        "recommendation_started requestId=%s strategy=%s algorithm=%s "
        "ratings=%d limit=%d",
        request_id,
        request.strategy,
        request.algorithm,
        len(request.ratings),
        request.limit,
    )
    try:
        result = recommend_movies(request)
        response = _to_recommendation_response(
            result=result,
            request_id=request_id,
        )
    except RecommendationServiceError as exc:
        logger.warning(
            "recommendation_failed requestId=%s strategy=%s algorithm=%s code=%s",
            request_id,
            request.strategy,
            request.algorithm,
            exc.code,
        )
        raise RecommendationHttpError(
            request_id=request_id,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status_code=exc.status_code,
        ) from exc
    except Exception as exc:
        logger.exception(
            "recommendation_failed requestId=%s strategy=%s algorithm=%s "
            "code=internal_recommendation_error",
            request_id,
            request.strategy,
            request.algorithm,
        )
        raise RecommendationHttpError(
            request_id=request_id,
            code="internal_recommendation_error",
            message="Unexpected internal recommendation error.",
            status_code=500,
        ) from exc

    logger.info(
        "recommendation_completed requestId=%s strategy=%s algorithm=%s "
        "recommendations=%d",
        request_id,
        result.strategy,
        result.algorithm,
        len(result.recommendations),
    )
    return response


def _to_recommendation_response(
    *,
    result: UnifiedRecommendationResult,
    request_id: str,
) -> RecommendationResponse:
    recommendation_items = [
        RecommendationItemResponse(
            rank=rank,
            movie=PublicMovieRecord.model_validate(
                catalog_repository.get_public_movie_by_id(item.movie_id)
            ),
            score=item.score,
            matchPercentage=item.match_percentage,
            explanation=RecommendationExplanation(
                summary=item.explanation.summary,
                reasons=item.explanation.reasons,
            ),
        )
        for rank, item in enumerate(result.recommendations, start=1)
    ]
    return RecommendationResponse(
        requestId=request_id,
        strategy=result.strategy,
        algorithm=result.algorithm,
        recommendations=recommendation_items,
        meta=RecommendationMeta(
            limit=result.limit,
            count=len(recommendation_items),
        ),
    )
