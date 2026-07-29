from __future__ import annotations

from dataclasses import dataclass

from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class UserMovieRating:
    movieId: int
    rating: float


@dataclass(frozen=True)
class ContentIndex:
    features: csr_matrix
    movies: list[dict]
    featureNames: list[str]
    metadata: dict
    movieIdToRowIndex: dict[int, int]


@dataclass(frozen=True)
class UserProfile:
    profileVector: csr_matrix
    positiveVector: csr_matrix
    negativeVector: csr_matrix
    ratedMovieIds: set[int]
    positiveRatedMovieIds: set[int]
    negativeRatedMovieIds: set[int]
    neutralRatedMovieIds: set[int]
    positiveSignals: list[str]
    negativeSignals: list[str]
    style: str
    ratedMovieCount: int
    positiveRatingCount: int
    negativeRatingCount: int
    neutralRatingCount: int


@dataclass(frozen=True)
class UserProfileSummary:
    style: str
    headline: str
    positiveSignals: list[str]
    negativeSignals: list[str]
    ratedMovieCount: int
    positiveRatingCount: int
    negativeRatingCount: int
    neutralRatingCount: int
    positiveRatedMovies: list[str]
    negativeRatedMovies: list[str]
    neutralRatedMovies: list[str]


@dataclass(frozen=True)
class ContentSimilarityCandidate:
    movieId: int
    displayTitle: str
    year: int | None
    suitabilityCategory: str
    standDisplayScore: float
    contentSimilarity: float
    genres: list[str]
    matchedSignals: list[str]


@dataclass(frozen=True)
class ScoredContentCandidate:
    movieId: int
    displayTitle: str
    year: int | None
    suitabilityCategory: str
    standDisplayScore: float
    contentSimilarity: float
    recommendationScore: float
    genres: list[str]
    matchedSignals: list[str]


@dataclass(frozen=True)
class DiversifiedContentCandidate:
    movieId: int
    displayTitle: str
    year: int | None
    suitabilityCategory: str
    standDisplayScore: float
    contentSimilarity: float
    recommendationScore: float
    mmrScore: float
    maxSimilarityToSelected: float
    genres: list[str]
    matchedSignals: list[str]


@dataclass(frozen=True)
class RecommendationExplanation:
    headline: str
    reasons: list[str]
    matchedSignals: list[str]
    avoidedSignals: list[str]
    similarRatedMovies: list[str]
    style: str


@dataclass(frozen=True)
class ExplainedContentRecommendation:
    movieId: int
    displayTitle: str
    year: int | None
    suitabilityCategory: str
    standDisplayScore: float
    recommendationScore: float
    contentSimilarity: float
    mmrScore: float
    genres: list[str]
    explanation: RecommendationExplanation


@dataclass(frozen=True)
class TemporaryMovieRating:
    movieId: int
    rating: int | float


@dataclass(frozen=True)
class ContentRecommendationRequest:
    ratings: list[TemporaryMovieRating]
    limit: int
    templateSessionId: str | None = None


@dataclass(frozen=True)
class ContentRecommendationProfileSummary:
    style: str
    headline: str
    ratedMovieCount: int
    nonNeutralRatingCount: int
    positiveRatingCount: int
    negativeRatingCount: int
    minimumRequiredRatings: int
    recommendedMinimumRatings: int
    confidence: str
    positiveSignals: list[str]
    negativeSignals: list[str]


@dataclass(frozen=True)
class ContentRecommendationItem:
    movieId: int
    displayTitle: str
    year: int | None
    genres: list[str]
    suitabilityCategory: str
    standDisplayScore: float
    recommendationScore: float
    contentSimilarity: float
    mmrScore: float
    explanation: RecommendationExplanation
    posterPath: str | None = None
    tmdbId: int | None = None
    originalTitle: str | None = None
    originalLanguage: str | None = None
    overview: str | None = None


@dataclass(frozen=True)
class ContentRecommendationResponse:
    profile: ContentRecommendationProfileSummary
    recommendations: list[ContentRecommendationItem]
    templateSessionId: str
    limit: int
