from sqlalchemy import String
from sqlalchemy.orm import mapped_column, Mapped

from app.core.db import Base

EMAIL_MAX_LENGTH = 100


class User(Base):
    """Класс пользователя."""

    email: Mapped[str] = mapped_column(
        String(EMAIL_MAX_LENGTH), unique=True
    )
