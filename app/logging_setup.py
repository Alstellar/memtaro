# app/logging_setup.py

import sys
from loguru import logger
import os


def setup_logging():
    """
    Настраивает Loguru для проекта с ротацией по дням.
    """
    # Убедимся, что папка logs существует
    os.makedirs("logs", exist_ok=True)

    # Удаляем стандартный обработчик
    logger.remove()

    # Логи в консоль (для разработки)
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:HH:mm:ss} | {level:<7} | {message}"
    )

    # Логи в файл с ежедневной ротацией
    logger.add(
        sink=f"logs/bot_{{time:YYYY-MM-DD}}.log",  # Имя файла будет "bot_2025-11-18.log"
        level="INFO",
        format="{time} | {level} | {message}",
        rotation="00:00",  # Новый файл каждый день в полночь
        retention="7 days",  # Хранить файлы логов за последние 7 дней
        compression="zip",  # Сжимать старые логи
        enqueue=True  # Асинхронная запись
    )

    logger.info("Система логирования настроена.")