import asyncpg
from loguru import logger
from datetime import datetime
from aiogram import Bot
from aiogram.enums import ChatMemberStatus

# Импортируем наши репозитории и конфиг
from app.config import BotSettings
from db.db_users import UserRepo
from db.db_predicts import PredictRepo
from db.db_statistics import StatisticsRepo


async def is_user_premium(user_id: int, user_repo: UserRepo) -> bool:
    """
    Проверяет, активна ли у пользователя подписка.
    """
    user_bd = await user_repo.get_user(user_id)
    if not user_bd:
        return False
    user_premium_date = user_bd.get("premium_date")
    now = datetime.now()
    return bool(user_premium_date and user_premium_date >= now)


async def ensure_user_records(
        user_id: int,
        predict_repo: PredictRepo,
        stats_repo: StatisticsRepo
):
    """
    Гарантирует, что у пользователя есть записи в predicts и statistics.
    """
    # Проверяем predicts
    predict_bd = await predict_repo.get_predicts(user_id)
    if predict_bd is None:
        await predict_repo.add_predicts(user_id)

    # Проверяем statistics
    stats_bd = await stats_repo.get_statistics_entry(user_id)
    if stats_bd is None:
        await stats_repo.add_statistics_entry(user_id)

