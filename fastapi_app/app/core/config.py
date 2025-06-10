from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    DB_URL: str
    ARI_PASS: str
    DEFAULT_TIMEZONE: str = Field('Europe/Moscow')
    APP_TITLE: str = Field('Нейро-Ассистент')
    APP_DESCRIPTION: str = Field('Отправляйте звонки на номера России')

    model_config = SettingsConfigDict(
        extra='ignore'
    )

    @property
    def timezone(self):
        return ZoneInfo(self.DEFAULT_TIMEZONE)


settings = Settings()
