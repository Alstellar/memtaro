# app/scheduler/jobs.py
import asyncio
from datetime import datetime
from loguru import logger
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
import asyncpg

from app.config import BotSettings
from app.services.safe_sender import safe_send_message

# Импортируем классы репозиториев
from db.db_users import UserRepo
from db.db_predicts import PredictRepo
from db.db_images import ImageRepo
from db.db_settings import SettingsRepo


async def send_daily_reminder(bot: Bot, pool: asyncpg.Pool, bot_settings: BotSettings):  # 👈 Добавлен bot_settings
    """
    Ежедневное напоминание (утром).
    """
    logger.info("Запуск рассылки утренних напоминаний...")
    user_repo = UserRepo(pool)
    predict_repo = PredictRepo(pool)
    # settings_repo = SettingsRepo(pool) # Не используется напрямую в цикле

    user_ids = await user_repo.get_sendable_user_ids()
    today = datetime.now().date()
    predicted_today_ids = await predict_repo.get_user_ids_with_predict_date(today)

    count_sent = 0
    count_skip = 0

    for uid in user_ids:
        if uid in predicted_today_ids:
            continue

        text_msg = (
            "Доброе утро! 🌞\n\n"
            "Готовы узнать, что сегодня для Вас приготовила судьба?\n\n"
            "• /mem — мем-предсказание 🔮\n"
            "• /wisdom — мудрость дня 🧙‍♂️\n"
            "• /menu — главное меню 🏠\n\n"
            "🪬 Хотите больше мистики? Загляните в "
            "<b><a href=\"https://t.me/rus_tarot_bot\">Таро | Гороскоп</a></b>.\n\n"
            "🌟 Удачного дня! 🌟"
        )

        if await safe_send_message(bot, uid, text_msg, user_repo):
            count_sent += 1
        else:
            count_skip += 1

        await asyncio.sleep(1.5)

    # 👇 ОТЧЕТ О РАССЫЛКЕ
    report = (
        "📊 <b>Отчет утренней рассылки:</b>\n"
        f"✅ Отправлено: <code>{count_sent}</code>\n"
        f"🚫 Пропущено (блок/ошибки): <code>{count_skip}</code>"
    )
    await safe_send_message(bot, bot_settings.LOG_GROUP_ID, report)
    logger.info(f"Напоминания: отправлено {count_sent}, ошибок/блоков {count_skip}")


async def send_daily_karma_bonus(bot: Bot, pool: asyncpg.Pool, bot_settings: BotSettings):
    """
    Ежедневное начисление фиксированной кармы подписчикам (Premium).
    """
    logger.info("Начисление ежедневных бонусов Premium...")
    user_repo = UserRepo(pool)
    settings_repo = SettingsRepo(pool)
    bonus = await settings_repo.get_setting_value("bonus_premium_daily_karma", 50)
    count = await user_repo.add_karma_to_active_premium_users(bonus)
    total_karma = count * bonus

    report = (
        "<b>Ежедневное начисление кармы (Premium)</b>\n\n"
        f"Пользователи: <code>{count}</code>\n"
        f"Начислено: <code>{total_karma}</code>✨"
    )
    await safe_send_message(bot, bot_settings.LOG_GROUP_ID, report)


async def send_daily_channel_bonus(bot: Bot, pool: asyncpg.Pool, bot_settings: BotSettings):
    """
    Проверка подписки на канал и начисление кармы (bonus_channel_sub).
    """
    logger.info("Проверка подписок на канал...")
    user_repo = UserRepo(pool)
    settings_repo = SettingsRepo(pool)
    bonus = await settings_repo.get_setting_value("bonus_channel_sub", 1)

    count_ok = 0
    count_unsub = 0

    for user in await user_repo.get_channel_bonus_candidates():
        uid = user["user_id"]

        try:
            member = await bot.get_chat_member(bot_settings.CHANNEL_ID, uid)
            is_sub = member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR,
                                       ChatMemberStatus.CREATOR)

            if is_sub:
                new_karma = user["karma"] + bonus
                await user_repo.update_user_profile_parameters(uid, karma=new_karma)
                count_ok += 1
            else:
                await user_repo.update_user_profile_parameters(uid, sub_my_freelancer_notes=False)
                count_unsub += 1

        except Exception as e:
            logger.error(f"Ошибка проверки подписки {uid}: {e}")
            await user_repo.update_user_profile_parameters(uid, sub_my_freelancer_notes=False)

        await asyncio.sleep(0.05)

    report = (
        "📋 <b>Проверка подписок на канал:</b>\n\n"
        f"Начислено бонусов (+{bonus}): <code>{count_ok}</code>\n"
        f"Отписались: <code>{count_unsub}</code>"
    )
    await safe_send_message(bot, bot_settings.LOG_GROUP_ID, report)


async def send_monthly_rating(bot: Bot, pool: asyncpg.Pool, bot_settings: BotSettings):
    """
    1-го числа месяца: Топ мемов, награды авторам и сброс счетчика просмотров.
    """
    logger.info("Подведение итогов месяца...")
    image_repo = ImageRepo(pool)
    user_repo = UserRepo(pool)
    settings_repo = SettingsRepo(pool)

    # --- 1. Динамические настройки ---
    limit = await settings_repo.get_setting_value("limit_top_memes", 10)
    meme_bonus = await settings_repo.get_setting_value("bonus_meme_top_karma_per_meme", 100)

    # --- 2. Логика наград за ТОП МЕМОВ ---

    top_memes = await image_repo.get_top_memes_month(limit=limit)

    report_lines = ["<b>🏆 Рейтинг самых просматриваемых мемов за месяц</b>\n"]
    processed_authors = set()

    for idx, record in enumerate(top_memes, start=1):
        line = (
            f"<b>{idx}.</b> ImgID: <code>{record['image_id']}</code> • "
            f"User: <code>{record['user_id']}</code> • "
            f"Views: <code>{record['watch_month']}</code>"
        )
        report_lines.append(line)

        author_id = record["user_id"]
        if author_id and author_id not in processed_authors:
            processed_authors.add(author_id)
            user = await user_repo.get_user(author_id)
            if user:
                new_karma = user["karma"] + meme_bonus
                await user_repo.update_user_profile_parameters(author_id, karma=new_karma)

                await safe_send_message(
                    bot, author_id,
                    f"🎉 <b>ПОБЕДА В ТОПЕ!</b> Ваш мем №{idx} вошел в ТОП-{limit} месяца! Начислено <b>+{meme_bonus}</b> ✨ кармы.",
                    user_repo
                )

                await asyncio.sleep(0.5)

    await safe_send_message(bot, bot_settings.LOG_GROUP_ID, "\n\n".join(report_lines))

    # --- 3. Сброс счетчиков ---
    await image_repo.reset_monthly_views()
    logger.info("Счетчики просмотров за месяц сброшены.")
