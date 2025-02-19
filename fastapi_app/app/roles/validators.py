from tortoise.validators import RegexValidator


class SlugValidator(RegexValidator):
    def __init__(self):
        """
        Вызываем родительский класс для валидатора, и передаем регулярку
        для slug полей.
        """
        super().__init__('^[a-z0-9]+(?:(?:-|_)+[a-z0-9]+)*$', flags=0)
