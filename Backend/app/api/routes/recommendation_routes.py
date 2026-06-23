from fastapi import APIRouter, HTTPException

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.content_based.models import (
    ContentRecommendationRequest as DomainContentRecommendationRequest,
    ContentRecommendationResponse as DomainContentRecommendationResponse,
    TemporaryMovieRating,
)
from app.recommenders.content_based.recommender import (
    ContentRecommendationDomainError,
    recommend_content_based_movies,
)
from app.schemas.catalog_schemas import PublicMovieRecord
from app.schemas.content_recommendation_schemas import (
    ContentBasedRecommendationRequest,
    ContentBasedRecommendationResponse,
    ContentRecommendationExplanation,
    ContentRecommendationItemResponse,
    ContentRecommendationProfileResponse,
    ContentRecommendationScores,
)
from app.schemas.error_schemas import ErrorResponse
from app.schemas.recommendation_schemas import RecommenderDetails


router = APIRouter(tags=["recommendations"])


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

    return _to_content_recommendation_response(response)


def _to_content_recommendation_response(
    response: DomainContentRecommendationResponse,
) -> ContentBasedRecommendationResponse:
    return ContentBasedRecommendationResponse(
        strategy="content_based",
        profile=ContentRecommendationProfileResponse.model_validate(
            response.profile,
            from_attributes=True,
        ),
        recommendations=[
            ContentRecommendationItemResponse(
                movieId=item.movieId,
                rank=rank,
                movie=PublicMovieRecord.model_validate(
                    catalog_repository.get_public_movie_by_id(item.movieId)
                ),
                scores=ContentRecommendationScores(
                    recommendationScore=item.recommendationScore,
                    contentSimilarity=item.contentSimilarity,
                    mmrScore=item.mmrScore,
                    standDisplayScore=item.standDisplayScore,
                ),
                explanation=ContentRecommendationExplanation.model_validate(
                    item.explanation,
                    from_attributes=True,
                ),
                algorithmDetails={
                    "contentSimilarity": item.contentSimilarity,
                    "mmrScore": item.mmrScore,
                    "standDisplayScore": item.standDisplayScore,
                    "matchedSignals": item.explanation.matchedSignals,
                },
            )
            for rank, item in enumerate(response.recommendations, start=1)
        ],
        recommenderDetails=RecommenderDetails(
            strategy="content_based",
            algorithmId="content_based_default",
            algorithmLabel="Content-based",
            isPersonalized=True,
            isExplainable=True,
            status="ready",
        ),
        templateSessionId=response.templateSessionId,
        limit=response.limit,
    )
