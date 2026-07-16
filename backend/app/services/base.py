"""
Abstract base service.

All domain services inherit from BaseService to receive a typed
reference to the async database session via dependency injection.
"""
from abc import ABC

from sqlalchemy.ext.asyncio import AsyncSession


class BaseService(ABC):
    """
    Base class for all SHM-AI business logic services.

    Receives an AsyncSession from the FastAPI DI system.
    Never instantiates repositories or other infrastructure directly —
    all dependencies are provided through constructor injection.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
