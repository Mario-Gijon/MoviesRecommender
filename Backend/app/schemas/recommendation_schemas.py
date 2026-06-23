from typing import Any, Literal

from pydantic import BaseModel, Field


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
    details: dict[str, Any] = Field(default_factory=dict)