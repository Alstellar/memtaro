import json
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    """Настройки подключения к основной базе данных."""

    class Config:
        env_file = ".env"
        env_prefix = "DB_"
        extra = "ignore"
        case_sensitive = False

    HOST: str
    PORT: int
    USER: str
    PASSWORD: SecretStr
    NAME: str

    def build_dsn(self) -> str:
        """Формирует DSN-строку для asyncpg."""
        return (
            f"postgresql://{self.USER}:{self.PASSWORD.get_secret_value()}"
            f"@{self.HOST}:{self.PORT}/{self.NAME}"
        )


class BotSettings(BaseSettings):
    """Настройки Telegram-бота."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    BOT_TOKEN: SecretStr
    ADMIN_IDS: list[int] = [600190760]
    LOG_GROUP_ID: int
    CHANNEL_ID: int

    YOOKASSA_SHOP_ID: int
    YOOKASSA_SECRET_KEY: SecretStr

    BOT_PROXY: Optional[str] = None
    BOT_PROXY_SCHEME: str = "http"

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        """Преобразует ADMIN_IDS из CSV/JSON в список целых чисел."""
        if isinstance(value, list):
            return [int(item) for item in value]

        if isinstance(value, int):
            return [value]

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []

            if raw.startswith("[") and raw.endswith("]"):
                parsed = json.loads(raw)
                return [int(item) for item in parsed]

            return [int(item.strip()) for item in raw.split(",") if item.strip()]

        return value

    @field_validator("BOT_PROXY_SCHEME", mode="before")
    @classmethod
    def normalize_proxy_scheme(cls, value):
        """Нормализует схему прокси и выставляет `http` по умолчанию."""
        if value is None:
            return "http"
        scheme = str(value).strip().lower()
        return scheme or "http"

    def build_proxy_url(self) -> Optional[str]:
        """Собирает URL прокси из полного или короткого формата."""
        raw = (self.BOT_PROXY or "").strip()
        if not raw:
            return None

        if "://" in raw:
            return raw

        parts = raw.split(":")
        if len(parts) not in (2, 4):
            raise ValueError(
                "BOT_PROXY должен быть в формате host:port или host:port:user:password, "
                "либо полным URL со схемой."
            )

        scheme = self.BOT_PROXY_SCHEME
        host, port = parts[0].strip(), parts[1].strip()
        if not host or not port:
            raise ValueError("BOT_PROXY должен содержать непустые host и port.")

        if len(parts) == 2:
            return f"{scheme}://{host}:{port}"

        user, password = parts[2], parts[3]
        user_q = quote(user, safe="")
        password_q = quote(password, safe="")
        return f"{scheme}://{user_q}:{password_q}@{host}:{port}"

    def masked_proxy_url(self) -> Optional[str]:
        """Возвращает URL прокси с маскировкой логина и пароля для логов."""
        proxy_url = self.build_proxy_url()
        if not proxy_url:
            return None

        parsed = urlsplit(proxy_url)
        if not parsed.username:
            return proxy_url

        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"***:***@{host}{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


class TarotDBSettings(BaseSettings):
    """Настройки подключения к БД проекта @rus_tarot_bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TAROT_DB_",
        extra="ignore",
        case_sensitive=False,
    )

    HOST: Optional[str] = None
    PORT: Optional[int] = None
    USER: Optional[str] = None
    PASSWORD: Optional[SecretStr] = None
    NAME: Optional[str] = None

    def is_configured(self) -> bool:
        """Проверяет, что все параметры TAROT_DB_* заполнены."""
        return all([self.HOST, self.PORT, self.USER, self.PASSWORD, self.NAME])

    def build_dsn(self) -> str:
        """Формирует DSN-строку для подключения к БД Tarot."""
        if not self.is_configured():
            raise ValueError("Tarot DB не настроена: заполните переменные TAROT_DB_*.")
        return (
            f"postgresql://{self.USER}:{self.PASSWORD.get_secret_value()}"
            f"@{self.HOST}:{self.PORT}/{self.NAME}"
        )


class Settings:
    """Объединяет все секции настроек приложения."""

    bot: BotSettings = BotSettings()
    db: DBSettings = DBSettings()
    tarot_db: TarotDBSettings = TarotDBSettings()


settings = Settings()
