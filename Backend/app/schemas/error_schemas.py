from pydantic import BaseModel, Field

from app.schemas.request_id_schemas import RequestId


class RecommendationError(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    requestId: RequestId
    error: RecommendationError
