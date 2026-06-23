from fastapi import APIRouter, HTTPException

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.common.errors import CollaborativeRecommendationError
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationRequest as DomainCollaborativeRecommendationRequest,
    CollaborativeRecommendationResult as DomainCollaborativeRecommendationResult,
    CollaborativeUserRating,
)
from app.recommenders.collaborative.service import recommend_collaborative_movies
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
from app.schemas.collaborative_recommendation_schemas import (
    CollaborativeRecommendationExplanation,
    CollaborativeRecommendationItemResponse,
    CollaborativeRecommendationProfileResponse,
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResponse,
    CollaborativeRecommendationScores,
)
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
from app.core.config import settings

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


@router.post(
    "/recommendations/collaborative",
    response_model=CollaborativeRecommendationResponse,
    responses={400: {"model": ErrorResponse}},
)
def create_collaborative_recommendations(
    payload: CollaborativeRecommendationRequest,
) -> CollaborativeRecommendationResponse:
    try:
        response = recommend_collaborative_movies(
            DomainCollaborativeRecommendationRequest(
                ratings=[
                    CollaborativeUserRating(movie_id=item.movieId, rating=item.rating)
                    for item in payload.ratings
                ],
                limit=payload.limit,
                template_session_id=payload.templateSessionId,
            ),
            algorithm_id=settings.active_collaborative_algorithm,
        )
    except CollaborativeRecommendationError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "message": "Unexpected collaborative recommendation error."},
        ) from exc

    return _to_collaborative_recommendation_response(
        response=response,
        request=payload,
    )


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


def _to_collaborative_recommendation_response(
    *,
    response: DomainCollaborativeRecommendationResult,
    request: CollaborativeRecommendationRequest,
) -> CollaborativeRecommendationResponse:
    return CollaborativeRecommendationResponse(
        strategy="collaborative",
        profile=_build_collaborative_profile(request),
        recommendations=[
            CollaborativeRecommendationItemResponse(
                movieId=item.movie_id,
                rank=item.rank,
                movie=PublicMovieRecord.model_validate(
                    catalog_repository.get_public_movie_by_id(item.movie_id)
                ),
                scores=CollaborativeRecommendationScores(
                    recommendationScore=item.score,
                    collaborativeScore=item.score,
                    popularityScore=item.score,
                ),
                explanation=CollaborativeRecommendationExplanation(
                    headline=item.explanation.headline,
                    reasons=item.explanation.reasons,
                    evidence=item.explanation.evidence,
                ),
                algorithmDetails=item.algorithm_details,
            )
            for item in response.recommendations
        ],
        recommenderDetails=RecommenderDetails(
            strategy="collaborative",
            algorithmId=response.recommender_details.algorithm_id,
            algorithmLabel=response.recommender_details.algorithm_label,
            modelVersion=response.recommender_details.model_version,
            isPersonalized=response.recommender_details.is_personalized,
            isExplainable=response.recommender_details.is_explainable,
            timingMs=response.recommender_details.timing_ms,
            status=response.recommender_details.status,
            details=response.recommender_details.details,
        ),
        templateSessionId=response.template_session_id,
        limit=response.limit,
    )


def _build_collaborative_profile(
    request: CollaborativeRecommendationRequest,
) -> CollaborativeRecommendationProfileResponse:
    non_neutral_rating_count = sum(1 for item in request.ratings if item.rating != 3)
    positive_rating_count = sum(1 for item in request.ratings if item.rating >= 4)
    negative_rating_count = sum(1 for item in request.ratings if item.rating <= 2)

    return CollaborativeRecommendationProfileResponse(
        style="baseline",
        headline="Baseline colaborativo basado en valoraciones agregadas.",
        ratedMovieCount=len(request.ratings),
        nonNeutralRatingCount=non_neutral_rating_count,
        positiveRatingCount=positive_rating_count,
        negativeRatingCount=negative_rating_count,
        confidence=_collaborative_confidence(non_neutral_rating_count),
    )


def _collaborative_confidence(non_neutral_rating_count: int) -> str:
    if non_neutral_rating_count < 5:
        return "low"
    if non_neutral_rating_count < 8:
        return "medium"
    return "high"