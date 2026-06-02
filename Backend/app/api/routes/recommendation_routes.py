from fastapi import APIRouter

from app.domain.recommendations.recommendation_schemas import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.domain.recommendations.recommendation_strategy import build_placeholder_response


router = APIRouter(tags=["recommendations"])


@router.post("/recommendations", response_model=RecommendationResponse)
def create_recommendations(payload: RecommendationRequest) -> RecommendationResponse:
    return build_placeholder_response(payload)

