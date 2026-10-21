"""
Custom exception classes for SHM-AI.

Keeping exceptions in one place makes it easy to:
- Add custom error codes
- Map to HTTP status codes in FastAPI exception handlers
- Produce consistent error responses
"""
from http import HTTPStatus


class SHMBaseException(Exception):
    """Base exception for all SHM-AI domain errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class EntityNotFoundError(SHMBaseException):
    """Raised when a requested database entity does not exist."""

    http_status = HTTPStatus.NOT_FOUND

    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity} with id '{entity_id}' was not found.",
            error_code="ENTITY_NOT_FOUND",
        )
        self.entity = entity
        self.entity_id = entity_id


class ValidationError(SHMBaseException):
    """Raised for domain-level validation failures (separate from Pydantic)."""

    http_status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="VALIDATION_ERROR")


class InferenceError(SHMBaseException):
    """Raised when the computer vision inference pipeline fails."""

    http_status = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="INFERENCE_ERROR")


class ModelNotFoundError(SHMBaseException):
    """Raised when configured vision model weights are missing from disk."""

    http_status = HTTPStatus.SERVICE_UNAVAILABLE

    def __init__(self, model_path: str, instruction: str | None = None) -> None:
        inst = instruction or (
            f"Configured vision model weights not found at '{model_path}'. "
            "Automatic weight downloads are disabled without explicit consent. "
            "To provision weights, place the weight file in the 'weights/' directory, "
            "or run: python scripts/download_weights.py"
        )
        super().__init__(message=inst, error_code="MODEL_WEIGHTS_MISSING")
        self.model_path = model_path
