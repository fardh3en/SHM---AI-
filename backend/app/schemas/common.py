"""
Common Pydantic v2 response schemas shared across all API endpoints.
"""
import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class SHMBaseSchema(BaseModel):
    """
    Shared Pydantic configuration for all SHM-AI schemas.

    - from_attributes=True enables ORM mode (SQLAlchemy → schema conversion)
    - populate_by_name=True allows using field names even when aliases are set
    - str_strip_whitespace=True prevents leading/trailing whitespace in string fields
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class PaginatedResponse(SHMBaseSchema, Generic[T]):
    """
    Generic paginated list response.

    Example response body::

        {
            "items": [...],
            "total": 42,
            "page": 1,
            "page_size": 20,
            "pages": 3
        }
    """
    items: list[T]
    total: int = Field(description="Total number of records matching the query.")
    page: int = Field(ge=1, description="Current page number (1-indexed).")
    page_size: int = Field(ge=1, le=100, description="Number of items per page.")
    pages: int = Field(description="Total number of pages.")

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """Factory method to construct a paginated response."""
        pages = max(1, math.ceil(total / page_size)) if page_size > 0 else 1
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class MessageResponse(SHMBaseSchema):
    """Simple success/message response for operations that don't return data."""
    message: str
    success: bool = True


class ErrorResponse(SHMBaseSchema):
    """
    Standard error response body.
    Returned on 4xx and 5xx HTTP responses.
    """
    detail: str = Field(description="Human-readable error description.")
    error_code: str | None = Field(
        default=None,
        description="Machine-readable error code for programmatic handling.",
    )
