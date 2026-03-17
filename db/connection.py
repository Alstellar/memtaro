import asyncpg
from loguru import logger

from app.config import settings


async def create_pool() -> asyncpg.Pool:
    """Создает пул соединений с основной PostgreSQL БД."""
    logger.info("Создание пула соединений с PostgreSQL...")
    try:
        pool = await asyncpg.create_pool(
            dsn=settings.db.build_dsn(),
            min_size=5,
            max_size=20,
        )
        logger.success("Пул соединений с основной БД успешно создан.")
        return pool
    except Exception as exc:
        logger.critical(f"Не удалось подключиться к основной БД: {exc}")
        raise


async def create_tarot_pool() -> asyncpg.Pool | None:
    """Создает пул к БД @rus_tarot_bot, если TAROT_DB_* заполнены."""
    if not settings.tarot_db.is_configured():
        logger.warning(
            "БД @rus_tarot_bot не настроена (TAROT_DB_*). "
            "Перенос кармы в Tarot временно недоступен."
        )
        return None

    logger.info("Создание пула соединений с БД @rus_tarot_bot...")
    try:
        pool = await asyncpg.create_pool(
            dsn=settings.tarot_db.build_dsn(),
            min_size=1,
            max_size=5,
        )
        logger.success("Пул соединений с БД @rus_tarot_bot успешно создан.")
        return pool
    except Exception as exc:
        logger.critical(f"Не удалось подключиться к БД @rus_tarot_bot: {exc}")
        raise
