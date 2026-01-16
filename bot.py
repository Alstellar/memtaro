# bot.py
import asyncio
import asyncpg
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Обновленные импорты
from app.config import settings
from app.logging_setup import setup_logging

from db.connection import create_pool

from db.init_db import create_tables
from db.db_users import UserRepo
from db.db_images import ImageRepo
from db.db_wisdom_images import WisdomImageRepo
from db.db_predicts import PredictRepo
from db.db_statistics import StatisticsRepo
from db.db_settings import SettingsRepo
from db.db_bot_images import BotImageRepo
from db.db_chats import ChatRepo
from db.db_payments import PaymentRepo
from db.db_activity import ActivityRepo

# ИМПОРТИРУЕМ РЕГИСТРАТОРЫ
from handlers import register_all_handlers

# Импорт планировщика
from app.scheduler.setup import setup_scheduler

async def main():
    # --- Настраиваем логирование ---
    setup_logging()

    # --- Создаем пул соединений ---
    pool = await create_pool()

    # --- Инициализация БД ---
    await create_tables(pool)

    # --- Создаем объекты Bot и Dispatcher ---
    bot = Bot(
        token=settings.bot.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # --- Создаем экземпляры репозиториев ---
    user_repo = UserRepo(pool)
    image_repo = ImageRepo(pool)
    wisdom_repo = WisdomImageRepo(pool)
    predict_repo = PredictRepo(pool)

    # --- Внедряем пул в Dispatcher (Dependency Injection) ---
    dp["pool"] = pool
    dp["bot_settings"] = settings.bot
    dp["user_repo"] = user_repo
    dp["image_repo"] = image_repo
    dp["wisdom_repo"] = wisdom_repo
    dp["predict_repo"] = predict_repo
    dp["stats_repo"] = StatisticsRepo(pool)
    dp["settings_repo"] = SettingsRepo(pool)
    dp["bot_image_repo"] = BotImageRepo(pool)
    dp["chat_repo"] = ChatRepo(pool)
    dp["payment_repo"] = PaymentRepo(pool)
    dp["activity_repo"] = ActivityRepo(pool)

    # РЕГИСТРИРУЕМ ХЭНДЛЕРЫ
    register_all_handlers(dp)

    # ЗАПУСК ПЛАНИРОВЩИКА
    scheduler = await setup_scheduler(bot, pool, settings.bot)
    scheduler.start()
    logger.info("Планировщик запущен.")

    logger.info("Запуск бота...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Остановка бота...")
        scheduler.shutdown()
        await pool.close()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Выход из программы.")