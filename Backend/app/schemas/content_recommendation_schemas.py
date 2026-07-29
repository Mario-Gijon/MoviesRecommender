from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog_schemas import PublicMovieRecord
from app.schemas.recommendation_schemas import (
    LegacyRecommendationStrategy,
    RecommenderDetails,
)


class ContentBasedRatingInput(BaseModel):
    movieId: int
    rating: int | float = Field(ge=1, le=5)


class ContentBasedRecommendationRequest(BaseModel):
    ratings: list[ContentBasedRatingInput]
    limit: int = Field(default=10, ge=1, le=50)
    templateSessionId: str | None = None


class ContentRecommendationExplanation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    headline: str
    reasons: list[str]
    matchedSignals: list[str]
    avoidedSignals: list[str]
    similarRatedMovies: list[str]
    style: str


class ContentRecommendationScores(BaseModel):
    recommendationScore: float
    contentSimilarity: float | None = None
    mmrScore: float | None = None
    standDisplayScore: float | None = None


class ContentRecommendationItemResponse(BaseModel):
    movieId: int
    rank: int
    movie: PublicMovieRecord
    scores: ContentRecommendationScores
    explanation: ContentRecommendationExplanation
    algorithmDetails: dict[str, object] = Field(default_factory=dict)


class ContentRecommendationProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    style: str
    headline: str
    ratedMovieCount: int
    nonNeutralRatingCount: int
    positiveRatingCount: int
    negativeRatingCount: int
    minimumRequiredRatings: int
    recommendedMinimumRatings: int
    confidence: Literal["low", "medium", "high"]
    positiveSignals: list[str]
    negativeSignals: list[str]


class ContentBasedRecommendationResponse(BaseModel):
    strategy: LegacyRecommendationStrategy
    profile: ContentRecommendationProfileResponse
    recommendations: list[ContentRecommendationItemResponse]
    recommenderDetails: RecommenderDetails
    templateSessionId: str
    limit: int
