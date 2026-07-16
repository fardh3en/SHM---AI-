"""
SQLAlchemy declarative base and shared model mixins.

All ORM models must inherit from Base (for table registration) and
optionally from TimestampedMixin and UUIDPrimaryKeyMixin.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base. All ORM models inherit from this."""
    pass


class UUIDPrimaryKeyMixin:
    """
    Adds a UUID string primary key named 'id'.

    UUID is generated client-side (Python) rather than server-side (DB)
    so we can reference the ID before the INSERT is flushed.
    """
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


class TimestampedMixin:
    """
    Adds created_at and updated_at audit timestamps.

    created_at — set once at INSERT time via server default.
    updated_at — updated automatically on every UPDATE via onupdate hook.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
