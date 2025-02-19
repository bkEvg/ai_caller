from tortoise.models import Model
from tortoise import fields

from .validators import SlugValidator

class Role(Model):
    """Класс представляющий роли для звонящего."""

    id = fields.IntField(primary_key=True)
    slug = fields.CharField(max_length=150, unique=True, validators=
        [SlugValidator()])
