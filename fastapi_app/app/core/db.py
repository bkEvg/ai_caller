from datetime import datetime
from functools import partial

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.orm import (sessionmaker, MappedColumn, mapped_column,
                            DeclarativeBase, declared_attr)
from sqlalchemy import DateTime

from .config import settings


now = partial(datetime.now, settings.timezone)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""

    id: MappedColumn[int] = mapped_column(primary_key=True)
    created_at: MappedColumn[datetime] = mapped_column(
        DateTime(True), default=datetime.now(settings.timezone)
    )
    updated_at: MappedColumn[datetime] = mapped_column(
        DateTime(True), default=datetime.now(settings.timezone),
        onupdate=datetime.now(settings.timezone)
    )

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


engine = create_async_engine(settings.DB_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)
