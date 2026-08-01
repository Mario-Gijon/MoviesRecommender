from fastapi import APIRouter, HTTPException

from app.domain.recommendations.content_based.recommender import (
    ContentRecommendationDomainError,
    recommend_content_based_movies,
)
from app.domain.recommendations.content_based.schemas import (
    ContentRecommendationResponse as DomainContentRecommendationResponse,
    ContentRecommendationRequest as DomainContentRecommendationRequest,
    TemporaryMovieRating,
)
from app.infrastructure.catalog.offline_catalog_repository import (
    OfflineCatalogDataUnavailableError,
    catalog_repository,
)
from app.domain.recommendations.recommendation_schemas import (
    ContentBasedRecommendationRequest,
    ContentBasedRecommendationResponse,
    ContentRecommendationExplanation,
    ContentRecommendationItemResponse,
    ContentRecommendationProfileResponse,
    ContentRecommendationScores,
    ErrorResponse,
    PublicMovieRecordResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.domain.recommendations.recommendation_strategy import build_placeholder_response


router = APIRouter(tags=["recommendations"])


@router.post("/recommendations", response_model=RecommendationResponse)
def create_recommendations(payload: RecommendationRequest) -> RecommendationResponse:
    try:
        return build_placeholder_response(payload)
    except OfflineCatalogDataUnavailableError as exc:
        raise _runtime_data_unavailable() from exc


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
        return _to_content_recommendation_response(response)
    except ContentRecommendationDomainError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    except OfflineCatalogDataUnavailableError as exc:
        raise _runtime_data_unavailable() from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "message": "Unexpected recommendation error."},
        ) from exc

def _to_content_recommendation_response(
    response: DomainContentRecommendationResponse,
) -> ContentBasedRecommendationResponse:
    return ContentBasedRecommendationResponse(
        profile=ContentRecommendationProfileResponse.model_validate(
            response.profile,
            from_attributes=True,
        ),
        recommendations=[
            ContentRecommendationItemResponse(
                movieId=item.movieId,
                movie=PublicMovieRecordResponse.model_validate(
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
            )
            for item in response.recommendations
        ],
        templateSessionId=response.templateSessionId,
        limit=response.limit,
    )


def _runtime_data_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "runtime_data_unavailable",
            "message": "Runtime dataset or recommender artifacts are unavailable.",
        },
    )
