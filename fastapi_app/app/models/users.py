from sqlalchemy import String
from sqlalchemy.orm import mapped_column, MappedColumn

from app.core.db import Base

EMAIL_MAX_LENGTH = 100


class User(Base):
    """Класс пользователя."""

    email: MappedColumn[str] = mapped_column(
        String(EMAIL_MAX_LENGTH), unique=True
    )
