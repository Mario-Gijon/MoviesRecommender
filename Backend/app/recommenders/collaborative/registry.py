from app.recommenders.collaborative.common.base import CollaborativeRecommender
from app.recommenders.collaborative.common.errors import (
    CollaborativeAlgorithmNotAvailableError,
)


COLLABORATIVE_RECOMMENDER_REGISTRY: dict[str, CollaborativeRecommender] = {}


def get_collaborative_recommender(algorithm_id: str) -> CollaborativeRecommender:
    recommender = COLLABORATIVE_RECOMMENDER_REGISTRY.get(algorithm_id)
    if recommender is None:
        raise CollaborativeAlgorithmNotAvailableError(
            code="collaborative_algorithm_not_available",
            message=f"Collaborative recommender algorithm is not available: {algorithm_id}",
        )
    return recommender
