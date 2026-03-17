import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from loguru import logger

from app.config import settings
from app.logging_setup import setup_logging
from app.scheduler.setup import setup_scheduler
from app.services.payment_service import restore_pending_payment_watchers
from db.connection import create_pool, create_tarot_pool
from db.db_activity import ActivityRepo
from db.db_bot_images import BotImageRepo
from db.db_chats import ChatRepo
from db.db_images import ImageRepo
from db.db_payments import PaymentRepo
from db.db_predicts import PredictRepo
from db.db_settings import SettingsRepo
from db.db_statistics import StatisticsRepo
from db.db_users import UserRepo
from db.db_wisdom_images import WisdomImageRepo
from db.init_db import create_tables
from handlers import register_all_handlers


async def main() -> None:
    """Инициализирует инфраструктуру и запускает polling бота."""
    setup_logging()

    pool = await create_pool()
    tarot_pool = await create_tarot_pool()
    await create_tables(pool)

    proxy_url = settings.bot.build_proxy_url()
    if proxy_url:
        logger.info(f"Запуск через proxy: {settings.bot.masked_proxy_url()}")
        bot_session = AiohttpSession(proxy=proxy_url)
    else:
        logger.info("Запуск без proxy.")
        bot_session = None

    bot = Bot(
        token=settings.bot.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=bot_session,
    )
    dp = Dispatcher()

    user_repo = UserRepo(pool)
    image_repo = ImageRepo(pool)
    wisdom_repo = WisdomImageRepo(pool)
    predict_repo = PredictRepo(pool)
    stats_repo = StatisticsRepo(pool)
    settings_repo = SettingsRepo(pool)
    payment_repo = PaymentRepo(pool)

    payment_task_registry: set[asyncio.Task] = set()

    dp["pool"] = pool
    dp["tarot_pool"] = tarot_pool
    dp["bot_settings"] = settings.bot
    dp["user_repo"] = user_repo
    dp["image_repo"] = image_repo
    dp["wisdom_repo"] = wisdom_repo
    dp["predict_repo"] = predict_repo
    dp["stats_repo"] = stats_repo
    dp["settings_repo"] = settings_repo
    dp["bot_image_repo"] = BotImageRepo(pool)
    dp["chat_repo"] = ChatRepo(pool)
    dp["payment_repo"] = payment_repo
    dp["activity_repo"] = ActivityRepo(pool)
    dp["payment_task_registry"] = payment_task_registry

    register_all_handlers(dp)

    scheduler = await setup_scheduler(bot, pool, settings.bot)
    scheduler.start()
    logger.info("Планировщик запущен.")

    recovered = await restore_pending_payment_watchers(
        bot=bot,
        payment_repo=payment_repo,
        user_repo=user_repo,
        stats_repo=stats_repo,
        settings_repo=settings_repo,
        pool=pool,
        task_registry=payment_task_registry,
    )
    if recovered:
        logger.info(f"Восстановлено фоновых проверок платежей: {recovered}")

    logger.info("Запуск бота...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Остановка бота...")
        scheduler.shutdown()

        if payment_task_registry:
            for task in list(payment_task_registry):
                task.cancel()
            await asyncio.gather(*payment_task_registry, return_exceptions=True)
            payment_task_registry.clear()

        await pool.close()
        if tarot_pool is not None:
            await tarot_pool.close()

        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Выход из программы.")
