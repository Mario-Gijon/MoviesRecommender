from uuid import uuid4

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.schemas.error_schemas import ErrorResponse, RecommendationError
from app.schemas.request_id_schemas import is_valid_request_id


CANONICAL_RECOMMENDATION_PATH = "/recommendations"


class RecommendationHttpError(RuntimeError):
    def __init__(
        self,
        *,
        request_id: str,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code


def generate_request_id() -> str:
    return f"rec-{uuid4()}"


def resolve_request_id(value: object | None) -> str:
    return value if is_valid_request_id(value) else generate_request_id()


async def recommendation_http_error_handler(
    request: Request,
    exc: RecommendationHttpError,
) -> JSONResponse:
    return _error_response(
        request_id=exc.request_id,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
    )


async def recommendation_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    if request.url.path != CANONICAL_RECOMMENDATION_PATH:
        return await request_validation_exception_handler(request, exc)

    request_id = _request_id_from_validation_body(exc.body)
    code, message, details = _normalize_validation_error(exc)
    return _error_response(
        request_id=request_id,
        code=code,
        message=message,
        details=details,
        status_code=422,
    )


def _request_id_from_validation_body(body: object) -> str:
    if isinstance(body, dict):
        request_id = body.get("requestId")
        if is_valid_request_id(request_id):
            return request_id
    return generate_request_id()


def _normalize_validation_error(
    exc: RequestValidationError,
) -> tuple[str, str, dict[str, object]]:
    errors = exc.errors()
    locations = [tuple(error.get("loc", ())) for error in errors]

    if any("limit" in location for location in locations):
        return (
            "invalid_limit",
            "limit must be an integer between 1 and 50.",
            {"minimum": 1, "maximum": 50},
        )
    if any("rating" in location for location in locations):
        return (
            "invalid_rating_value",
            "Every rating must be an integer between 1 and 5.",
            {"minimum": 1, "maximum": 5},
        )
    if any("ratings" in location for location in locations):
        return (
            "invalid_ratings",
            "ratings must be an array of movie ratings.",
            {},
        )
    return (
        "invalid_request",
        "The recommendation request is invalid.",
        {},
    )


def _error_response(
    *,
    request_id: str,
    code: str,
    message: str,
    details: dict[str, object],
    status_code: int,
) -> JSONResponse:
    payload = ErrorResponse(
        requestId=request_id,
        error=RecommendationError(
            code=code,
            message=message,
            details=details,
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )
