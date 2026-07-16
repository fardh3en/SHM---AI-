"""
Generic async CRUD repository.

Implements the Repository pattern to completely decouple data-access logic
from business logic. All domain repositories extend BaseRepository[ModelT]
and inherit create / read / update / delete operations.

Design:
- Generic over ModelT (the SQLAlchemy ORM model)
- All queries use SQLAlchemy 2.0 select() API (no legacy Query API)
- Pagination is built-in — returns (items, total_count) tuples
- No business logic here — pure data access only
"""
import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic async CRUD repository.

    Subclass this and set the `model` class attribute::

        class AssetRepository(BaseRepository[Asset]):
            model = Asset
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: str) -> ModelT | None:
        """Fetch a single record by primary key. Returns None if not found."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        filters: list[Any] | None = None,
        order_by: Any | None = None,
    ) -> tuple[list[ModelT], int]:
        """
        Fetch a paginated list of records.

        Args:
            page: 1-indexed page number.
            page_size: Number of records per page.
            filters: Optional list of SQLAlchemy WHERE clause expressions.
            order_by: Optional ORDER BY expression.

        Returns:
            (items, total_count) tuple.
        """
        base_query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        if filters:
            for condition in filters:
                base_query = base_query.where(condition)
                count_query = count_query.where(condition)

        if order_by is not None:
            base_query = base_query.order_by(order_by)

        total: int = (await self.session.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        raw = await self.session.execute(base_query.offset(offset).limit(page_size))
        items: list[ModelT] = list(raw.scalars().all())

        return items, total

    async def create(self, **kwargs: Any) -> ModelT:
        """
        Instantiate and persist a new record.

        A UUID is generated automatically if 'id' is not provided in kwargs.
        """
        if "id" not in kwargs:
            kwargs["id"] = str(uuid.uuid4())
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()        # assigns DB-generated defaults
        await self.session.refresh(instance)  # re-load from DB
        return instance

    async def update(self, entity: ModelT, **kwargs: Any) -> ModelT:
        """
        Update fields on an existing record.

        Only fields present in kwargs and matching model attributes are updated.
        None values are skipped (use explicit sentinel if you need to null a field).
        """
        for key, value in kwargs.items():
            if hasattr(entity, key) and value is not None:
                setattr(entity, key, value)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update_fields(self, entity: ModelT, **kwargs: Any) -> ModelT:
        """
        Like update() but also sets None values (useful for explicit nulling).
        """
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Permanently delete a record. Caller must ensure FK constraints."""
        await self.session.delete(entity)
        await self.session.flush()

    async def exists(self, entity_id: str) -> bool:
        """Return True if a record with the given ID exists."""
        result = await self.session.execute(
            select(func.count())
            .select_from(self.model)
            .where(self.model.id == entity_id)  # type: ignore[attr-defined]
        )
        return (result.scalar_one() or 0) > 0

    async def bulk_create(self, records: Sequence[dict[str, Any]]) -> list[ModelT]:
        """Efficiently insert multiple records in a single flush."""
        instances = []
        for data in records:
            if "id" not in data:
                data = {**data, "id": str(uuid.uuid4())}
            instances.append(self.model(**data))
        self.session.add_all(instances)
        await self.session.flush()
        return instances
