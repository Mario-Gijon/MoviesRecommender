from typing import Annotated, TypeGuard

from pydantic import AfterValidator, Field


REQUEST_ID_MAX_LENGTH = 128


def is_valid_request_id(value: object) -> TypeGuard[str]:
    return (
        isinstance(value, str)
        and len(value) <= REQUEST_ID_MAX_LENGTH
        and bool(value.strip())
    )


def validate_request_id(value: str) -> str:
    if not is_valid_request_id(value):
        raise ValueError(
            "requestId must contain a non-whitespace character and be at most "
            f"{REQUEST_ID_MAX_LENGTH} characters long."
        )
    return value


RequestId = Annotated[
    str,
    Field(strict=True, max_length=REQUEST_ID_MAX_LENGTH),
    AfterValidator(validate_request_id),
]
