from fastapi import APIRouter, HTTPException

from app.domain.recommendations.content_based.recommender import (
    ContentRecommendationDomainError,
    recommend_content_based_movies,
)
from app.domain.recommendations.content_based.schemas import (
    ContentRecommendationRequest as DomainContentRecommendationRequest,
    TemporaryMovieRating,
)
from app.domain.recommendations.recommendation_schemas import (
    ContentBasedRecommendationRequest,
    ContentBasedRecommendationResponse,
    ErrorResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.domain.recommendations.recommendation_strategy import build_placeholder_response


router = APIRouter(tags=["recommendations"])


@router.post("/recommendations", response_model=RecommendationResponse)
def create_recommendations(payload: RecommendationRequest) -> RecommendationResponse:
    return build_placeholder_response(payload)


@router.post(
    "/recommendations/content-based",
    response_model=ContentBasedRecommendationResponse,
    responses={400: {"model": ErrorResponse}},
)
def create_content_based_recommendations(
    payload: ContentBasedRecommendationRequest,
) -> ContentBasedRecommendationResponse:
    try:
        response = recommend_content_based_movies(
            DomainContentRecommendationRequest(
                ratings=[
                    TemporaryMovieRating(movieId=item.movieId, rating=item.rating)
                    for item in payload.ratings
                ],
                limit=payload.limit,
                templateSessionId=payload.templateSessionId,
            )
        )
    except ContentRecommendationDomainError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "message": "Unexpected recommendation error."},
        ) from exc

    return ContentBasedRecommendationResponse(
        profile=response.profile,
        recommendations=response.recommendations,
        templateSessionId=response.templateSessionId,
        limit=response.limit,
    )
