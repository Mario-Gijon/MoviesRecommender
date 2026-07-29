from pydantic import BaseModel, Field


class ContentBasedRatingInput(BaseModel):
    movieId: int
    rating: int = Field(ge=1, le=5)


class ContentBasedRecommendationRequest(BaseModel):
    requestId: str | None = Field(default=None, min_length=1)
    ratings: list[ContentBasedRatingInput]
    limit: int = Field(default=10, ge=1, le=50)
    templateSessionId: str | None = None
