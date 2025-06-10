from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    ari_pass: str = Field(..., alias='ARI_PASS')
    db_url: str
    default_timezone: str = Field('Europe/Moscow')
    app_title: str = Field('Нейро-Ассистент')
    app_description: str = Field('Отправляйте звонки на номера России')

    model_config = SettingsConfigDict(
        extra='ignore', env_file='.env', case_sensitive=False
    )

    @property
    def timezone(self):
        return ZoneInfo(self.default_timezone)


settings = Settings()
