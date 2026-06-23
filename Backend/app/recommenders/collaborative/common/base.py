from typing import Protocol

from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationRequest,
    CollaborativeRecommendationResult,
)


class CollaborativeRecommender(Protocol):
    algorithm_id: str
    algorithm_label: str

    def recommend(
        self,
        request: CollaborativeRecommendationRequest,
    ) -> CollaborativeRecommendationResult: ...
