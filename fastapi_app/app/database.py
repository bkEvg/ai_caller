from tortoise import Tortoise

from .constants import POSTGRES_URL

TORTOISE_ORM = {
    "connections": {
        "default": POSTGRES_URL
    },
    "apps": {
        "models": {
            "models": [
                "app.users.models",
                "app.roles.models",
                "aerich.models"
            ],
            "default_connection": "default",
        }
    }
}

async def init_db():
    """Инициализация бд."""
    await Tortoise.init(config=TORTOISE_ORM)
