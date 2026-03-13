# app/config.py
import json

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    """Настройки подключения к БД"""

    # Для pydantic v1 (и v2)
    class Config:
        env_file = ".env"
        env_prefix = "DB_"  # Искать переменные .env, которые начинаются с DB_

        extra = "ignore"  # Игнорировать 'BOT_TOKEN'
        case_sensitive = False  # 'DB_HOST' == 'db_host'

    HOST: str
    PORT: int
    USER: str
    PASSWORD: SecretStr
    NAME: str

    # Собираем DSN (Data Source Name) для asyncpg
    def build_dsn(self) -> str:
        return (
            f"postgresql://{self.USER}:{self.PASSWORD.get_secret_value()}"
            f"@{self.HOST}:{self.PORT}/{self.NAME}"
        )


class BotSettings(BaseSettings):
    """Настройки бота"""

    # Это конфиг для Pydantic v2
    model_config = SettingsConfigDict(
        env_file='.env',
        extra='ignore',  #
        case_sensitive=False  #
    )

    BOT_TOKEN: SecretStr  #
    ADMIN_IDS: list[int] = [600190760]

    LOG_GROUP_ID: int = -1002253945835
    CHANNEL_ID: int = -1001204551737

    # ЮКасса
    YOOKASSA_SHOP_ID: int
    YOOKASSA_SECRET_KEY: SecretStr

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        """
        Supports both CSV format ("1,2,3") and JSON array ("[1,2,3]").
        """
        if isinstance(value, list):
            return [int(item) for item in value]

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []

            if raw.startswith("[") and raw.endswith("]"):
                parsed = json.loads(raw)
                return [int(item) for item in parsed]

            return [int(item.strip()) for item in raw.split(",") if item.strip()]

        return value


class Settings:
    """Главный класс настроек, объединяющий остальные"""
    bot: BotSettings = BotSettings()
    db: DBSettings = DBSettings()


# Создаем один экземпляр, который будем импортировать везде
settings = Settings()
