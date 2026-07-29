from pydantic import BaseModel, Field


class RecommendationError(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    requestId: str
    error: RecommendationError
