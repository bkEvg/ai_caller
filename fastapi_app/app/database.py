from tortoise import Tortoise

from constants import POSTGRES_URL


async def init_db():
    """Инициализация бд, создание таблиц и тд."""
    await Tortoise.init(
        db_url=POSTGRES_URL,
        modules={'models': ['app.models']}
    )
    await Tortoise.generate_schemas()
