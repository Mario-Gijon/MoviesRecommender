from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.catalog_schemas import PublicMovieRecord
from app.schemas.recommendation_schemas import RecommendationStrategy, RecommenderDetails


class CollaborativeRatingInput(BaseModel):
    movieId: int
    rating: int = Field(ge=1, le=5)


class CollaborativeRecommendationRequest(BaseModel):
    ratings: list[CollaborativeRatingInput]
    limit: int = Field(default=10, ge=1, le=50)
    templateSessionId: str | None = None


class CollaborativeRecommendationExplanation(BaseModel):
    headline: str
    reasons: list[str]
    evidence: list[str] = Field(default_factory=list)


class CollaborativeRecommendationScores(BaseModel):
    recommendationScore: float
    collaborativeScore: float | None = None
    popularityScore: float | None = None


class CollaborativeRecommendationItemResponse(BaseModel):
    movieId: int
    rank: int
    movie: PublicMovieRecord
    scores: CollaborativeRecommendationScores
    explanation: CollaborativeRecommendationExplanation
    algorithmDetails: dict[str, Any] = Field(default_factory=dict)


class CollaborativeRecommendationProfileResponse(BaseModel):
    style: str
    headline: str
    ratedMovieCount: int
    nonNeutralRatingCount: int
    positiveRatingCount: int
    negativeRatingCount: int
    confidence: Literal["low", "medium", "high"]


class CollaborativeRecommendationResponse(BaseModel):
    strategy: RecommendationStrategy
    profile: CollaborativeRecommendationProfileResponse
    recommendations: list[CollaborativeRecommendationItemResponse]
    recommenderDetails: RecommenderDetails
    templateSessionId: str | None
    limit: int