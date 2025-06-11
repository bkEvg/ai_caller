from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    ARI_PASS: str
    DEFAULT_TIMEZONE: str = Field('Europe/Moscow')
    APP_TITLE: str = Field('Нейро-Ассистент')
    APP_DESCRIPTION: str = Field('Отправляйте звонки на номера России')

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str = Field("5432")
    POSTGRES_DB: str

    model_config = SettingsConfigDict(
        extra='ignore'
    )

    @property
    def timezone(self):
        return ZoneInfo(self.DEFAULT_TIMEZONE)

    @property
    def DB_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
