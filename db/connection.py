import asyncpg
from loguru import logger

# Импортируем настройки из пакета app
from app.config import settings

async def create_pool() -> asyncpg.Pool:
    """
    Создает и возвращает пул соединений с базой данных.
    """
    logger.info("Создание пула соединений с PostgreSQL...")
    try:
        pool = await asyncpg.create_pool(
            dsn=settings.db.build_dsn(),
            min_size=5,
            max_size=20
        )
        logger.success("Пул соединений успешно создан.")
        return pool
    except Exception as e:
        logger.critical(f"Не удалось подключиться к базе данных: {e}")
        raise