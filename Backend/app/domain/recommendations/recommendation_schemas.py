from typing import Literal

from pydantic import BaseModel, Field

from app.domain.movies.movie_schemas import Movie


StrategyType = Literal["content", "collaborative", "hybrid"]


class RatingInput(BaseModel):
    movieId: int
    rating: int = Field(ge=1, le=5)


class RecommendationRequest(BaseModel):
    strategy: StrategyType
    ratings: list[RatingInput]


class ExplanationSignal(BaseModel):
    label: str
    value: str


class RecommendationItem(BaseModel):
    movie: Movie
    score: float
    matchPercentage: int
    method: str
    explanationSummary: str
    explanationSignals: list[ExplanationSignal]


class UserProfile(BaseModel):
    ratedMoviesCount: int
    averageRating: float
    favoriteGenres: list[str]
    selectedStrategy: StrategyType


class RecommendationExplanation(BaseModel):
    summary: str
    transparencyNotes: list[str]


class RecommendationResponse(BaseModel):
    strategy: StrategyType
    userProfile: UserProfile
    recommendations: list[RecommendationItem]
    explanation: RecommendationExplanation

