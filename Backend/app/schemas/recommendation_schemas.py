from typing import Literal

from pydantic import BaseModel


RecommendationStrategy = Literal["content_based", "collaborative", "hybrid"]


class RecommenderDetails(BaseModel):
    strategy: RecommendationStrategy
    algorithmId: str
    algorithmLabel: str
    modelVersion: str | None = None
    isPersonalized: bool
    isExplainable: bool
    timingMs: float | None = None
    status: str
