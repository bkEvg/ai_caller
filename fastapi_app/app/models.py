from tortoise.models import Model
from tortoise import fields


class User(Model):
    """Модель пользователя."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=150)
    email = fields.CharField(max_length=150, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = 'users'
