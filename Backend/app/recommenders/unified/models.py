from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RecommendationRating:
    movie_id: int
    rating: int


@dataclass(frozen=True)
class UnifiedRecommendationRequest:
    strategy: str
    algorithm: str
    ratings: list[RecommendationRating]
    limit: int


@dataclass(frozen=True)
class UnifiedRecommendationExplanation:
    summary: str
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UnifiedRecommendedMovie:
    movie_id: int
    score: float
    match_percentage: float
    explanation: UnifiedRecommendationExplanation


@dataclass(frozen=True)
class UnifiedRecommendationResult:
    strategy: str
    algorithm: str
    recommendations: list[UnifiedRecommendedMovie]
    limit: int


@dataclass(frozen=True)
class RecommendationServiceError(RuntimeError):
    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)
    status_code: int = 400

    def __str__(self) -> str:
        return self.message


class RecommendationAdapter(Protocol):
    def validate(
        self,
        request: UnifiedRecommendationRequest,
    ) -> None: ...

    def recommend(
        self,
        request: UnifiedRecommendationRequest,
    ) -> list[UnifiedRecommendedMovie]: ...
