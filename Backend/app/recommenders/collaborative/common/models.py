from dataclasses import dataclass, field
from typing import Any, Literal

CollaborativeRecommendationStatus = Literal["ready", "experimental", "unavailable"]

@dataclass(frozen=True)
class CollaborativeUserRating:
    movie_id: int
    rating: int


@dataclass(frozen=True)
class CollaborativeRecommendationRequest:
    ratings: list[CollaborativeUserRating]
    limit: int
    template_session_id: str | None = None


@dataclass(frozen=True)
class CollaborativeRecommendationExplanation:
    headline: str
    reasons: list[str]
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CollaborativeRecommendedMovie:
    movie_id: int
    rank: int
    score: float
    explanation: CollaborativeRecommendationExplanation
    algorithm_details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollaborativeRecommenderDetails:
    algorithm_id: str
    algorithm_label: str
    is_personalized: bool
    is_explainable: bool
    status: CollaborativeRecommendationStatus
    model_version: str | None = None
    timing_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollaborativeRecommendationResult:
    recommendations: list[CollaborativeRecommendedMovie]
    recommender_details: CollaborativeRecommenderDetails
    limit: int
    template_session_id: str | None = None
