from typing import Union
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    ari_pass: str
    db_url: str
    default_timezone: str = Field('Europe/Moscow')

    model_config = SettingsConfigDict(
        extra='ignore', env_file='.env'
    )

    @property
    def timezone(self):
        return ZoneInfo(self.default_timezone)


settings = Settings()
