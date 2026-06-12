from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(from_attributes=True)

    headline: str
    reasons: list[str]
    matchedSignals: list[str]
    avoidedSignals: list[str]
    similarRatedMovies: list[str]
    style: str


class ContentRecommendationScores(BaseModel):
    recommendationScore: float
    contentSimilarity: float
    mmrScore: float
    standDisplayScore: float


class PublicMovieRecordResponse(BaseModel):
    movieId: int
    tmdbId: int | None = None
    imdbId: str | None = None
    title: str
    cleanTitle: str | None = None
    originalTitle: str | None = None
    displayTitle: str
    year: int
    overview: str | None = None
    displayOverview: str | None = None
    genres: list[str]
    displayGenres: list[str]
    keywords: list[str]
    userTags: list[str]
    topCast: list[str]
    directors: list[str]
    posterPath: str | None = None
    posterFile: str | None = None
    runtime: int | None = None
    originalLanguage: str | None = None
    ratingCount: int | None = None
    averageRating: float | None = None
    filteredRatingCount: int | None = None
    filteredAverageRating: float | None = None
    candidateScore: float | None = None
    dataReliabilityScore: float | None = None
    recencyScore: float | None = None
    tmdbPopularity: float | None = None
    tmdbVoteAverage: float | None = None
    tmdbVoteCount: int | None = None
    suitabilityCategory: str | None = None
    standDisplayScore: float | None = None
    standDisplayReasons: list[str]
    posterUrl: str | None = None


class ContentRecommendationItemResponse(BaseModel):
    movieId: int
    movie: PublicMovieRecordResponse
    scores: ContentRecommendationScores
    explanation: ContentRecommendationExplanation


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
    model_config = ConfigDict(from_attributes=True)

    profile: ContentRecommendationProfileResponse
    recommendations: list[ContentRecommendationItemResponse]
    templateSessionId: str
    limit: int


class ErrorResponse(BaseModel):
    code: str
    message: str
