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


MethodType = Literal["content", "collaborative", "popularity", "diversity"]
ExplanationSignalType = Literal[
    "content_match",
    "collaborative_match",
    "quality_signal",
    "diversity_signal",
    "coverage_note",
]


class MethodContribution(BaseModel):
    method: MethodType
    weight: float
    score: float
    label: str


class ExplanationSignal(BaseModel):
    type: ExplanationSignalType
    label: str
    value: str
    weight: float | None = None


class RecommendationItem(BaseModel):
    movie: Movie
    score: float
    matchPercentage: int
    method: StrategyType
    methodContributions: list[MethodContribution]
    explanationSummary: str
    explanationSignals: list[ExplanationSignal]


class UserProfile(BaseModel):
    ratedMoviesCount: int
    averageRating: float
    favoriteGenres: list[str]
    favoriteTags: list[str]
    selectedStrategy: StrategyType


class RecommendationExplanation(BaseModel):
    summary: str
    transparencyNotes: list[str]


class RecommendationResponse(BaseModel):
    strategy: StrategyType
    userProfile: UserProfile
    recommendations: list[RecommendationItem]
    explanation: RecommendationExplanation
