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


class ContentBasedRatingInput(BaseModel):
    movieId: int
    rating: int | float = Field(ge=1, le=5)


class ContentBasedRecommendationRequest(BaseModel):
    ratings: list[ContentBasedRatingInput]
    limit: int = Field(default=10, ge=1, le=50)
    templateSessionId: str | None = None


class ContentRecommendationExplanation(BaseModel):
    headline: str
    reasons: list[str]
    matchedSignals: list[str]
    avoidedSignals: list[str]
    similarRatedMovies: list[str]
    style: str


class ContentRecommendationItemResponse(BaseModel):
    movieId: int
    displayTitle: str
    year: int | None = None
    genres: list[str]
    suitabilityCategory: str
    standDisplayScore: float
    recommendationScore: float
    contentSimilarity: float
    mmrScore: float
    explanation: ContentRecommendationExplanation
    posterPath: str | None = None
    tmdbId: int | None = None
    originalTitle: str | None = None
    originalLanguage: str | None = None
    overview: str | None = None


class ContentRecommendationProfileResponse(BaseModel):
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
    profile: ContentRecommendationProfileResponse
    recommendations: list[ContentRecommendationItemResponse]
    templateSessionId: str
    limit: int


class ErrorResponse(BaseModel):
    code: str
    message: str
