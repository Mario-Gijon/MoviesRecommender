from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationInput,
    CollaborativeRecommendationResult,
)
from app.recommenders.collaborative.registry import get_collaborative_recommender


def recommend_collaborative_movies(
    request: CollaborativeRecommendationInput,
    *,
    algorithm_id: str,
) -> CollaborativeRecommendationResult:
    recommender = get_collaborative_recommender(algorithm_id)
    return recommender.recommend(request)
