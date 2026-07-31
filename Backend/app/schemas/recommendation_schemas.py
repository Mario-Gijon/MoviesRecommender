from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog_schemas import PublicMovieRecord
from app.schemas.request_id_schemas import RequestId


RecommendationStrategy = Literal["content", "collaborative"]

StrictMovieId = Annotated[int, Field(strict=True, ge=1)]
StrictRating = Annotated[int, Field(strict=True, ge=1, le=5)]
StrictLimit = Annotated[int, Field(strict=True, ge=1, le=50)]


class RecommendationContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecommendationRatingInput(RecommendationContractModel):
    movieId: StrictMovieId
    rating: StrictRating


class RecommendationRequest(RecommendationContractModel):
    requestId: RequestId | None = None
    strategy: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)
    ratings: list[RecommendationRatingInput]
    limit: StrictLimit = 10


class RecommendationExplanation(RecommendationContractModel):
    summary: str
    reasons: list[str] = Field(default_factory=list)


class RecommendationItemResponse(RecommendationContractModel):
    rank: int = Field(ge=1)
    movie: PublicMovieRecord
    score: float
    matchPercentage: float = Field(ge=0, le=100)
    explanation: RecommendationExplanation


class RecommendationMeta(RecommendationContractModel):
    limit: int = Field(ge=1, le=50)
    count: int = Field(ge=0)


class RecommendationResponse(RecommendationContractModel):
    requestId: RequestId
    strategy: RecommendationStrategy
    algorithm: str
    recommendations: list[RecommendationItemResponse]
    meta: RecommendationMeta
