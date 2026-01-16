# app/scheduler/setup.py
import asyncpg
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import BotSettings
from app.scheduler.jobs import (
    send_daily_reminder,
    send_daily_karma_bonus,
    send_daily_channel_bonus,
    send_monthly_rating
)

async def setup_scheduler(bot: Bot, pool: asyncpg.Pool, bot_settings: BotSettings) -> AsyncIOScheduler:
    """
    Настраивает и возвращает планировщик задач.
    """
    scheduler = AsyncIOScheduler()

    # 1. Ежедневное напоминание в 9:00 (Теперь получает bot_settings)
    scheduler.add_job(
        send_daily_reminder,
        trigger=CronTrigger(hour=9, minute=0),
        kwargs={"bot": bot, "pool": pool, "bot_settings": bot_settings} # 👈 ИСПРАВЛЕНО
    )

    # 2. Бонус Premium в 00:05
    scheduler.add_job(
        send_daily_karma_bonus,
        trigger=CronTrigger(hour=0, minute=5),
        kwargs={"bot": bot, "pool": pool, "bot_settings": bot_settings}
    )

    # 3. Бонус за канал в 00:10
    scheduler.add_job(
        send_daily_channel_bonus,
        trigger=CronTrigger(hour=0, minute=10),
        kwargs={"bot": bot, "pool": pool, "bot_settings": bot_settings}
    )

    # 4. Итоги месяца (1-е число)
    scheduler.add_job(
        send_monthly_rating,
        trigger=CronTrigger(day=1, hour=8, minute=30),
        kwargs={"bot": bot, "pool": pool, "bot_settings": bot_settings}
    )

    return scheduler