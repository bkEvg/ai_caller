# Прокси модуль для испльзования в миграциях alembic
from app.core.db import Base  # noqa
from app.models.users import User  # noqa
from app.models.ai_agent import Call, CallStatus  # noqa
