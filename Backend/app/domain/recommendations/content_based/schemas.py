from __future__ import annotations

from dataclasses import dataclass

from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class UserMovieRating:
    movieId: int
    rating: int


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
