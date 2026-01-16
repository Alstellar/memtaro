# app/scheduler/jobs.py
import asyncio
from datetime import datetime
from loguru import logger
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
import asyncpg
from typing import Union, Optional

from app.config import BotSettings
from app.services.safe_sender import safe_send_message
from app.services.user_service import is_user_premium

# Импортируем классы репозиториев
from db.db_users import UserRepo
from db.db_predicts import PredictRepo
from db.db_images import ImageRepo
from db.db_settings import SettingsRepo
from db.db_statistics import StatisticsRepo


async def send_daily_reminder(bot: Bot, pool: asyncpg.Pool, bot_settings: BotSettings):  # 👈 Добавлен bot_settings
    """
    Ежедневное напоминание (утром).
    """
    logger.info("Запуск рассылки утренних напоминаний...")
    user_repo = UserRepo(pool)
    predict_repo = PredictRepo(pool)
    # settings_repo = SettingsRepo(pool) # Не используется напрямую в цикле

    user_ids = await user_repo.get_all_user_ids()
    today = datetime.now().date()

    count_sent = 0
    count_skip = 0

    for uid in user_ids:
        user = await user_repo.get_user(uid)
        if not user or not user.get("can_send_msg", True):
            continue

        predict = await predict_repo.get_predicts(uid)
        if predict and predict.get('last_predict_date') == today:
            continue

        text_msg = (
            "Доброе утро! 🌞\n\n"
            "Готовы узнать, что сегодня для Вас приготовила судьба?\n\n"
            "Введите /mem, чтобы получить ваше персональное мем-предсказание 🔮\n\n"
            "Введите /wisdom, чтобы получить мудрость дня 🧙‍♂️\n\n"
            "🔥 А еще у нас стартовала <b>Снежная битва!!!</b>\n\n"
            "Подробнее - /snow_info\n\n"
            "🌟 Хорошего дня! 🌟"
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
    user_ids = await user_repo.get_all_user_ids()

    bonus = await settings_repo.get_setting_value("bonus_premium_daily_karma", 50)

    count = 0
    total_karma = 0

    for uid in user_ids:
        if await is_user_premium(uid, user_repo):
            user = await user_repo.get_user(uid)
            new_karma = user["karma"] + bonus
            await user_repo.update_user_profile_parameters(uid, karma=new_karma)
            count += 1
            total_karma += bonus

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
    user_ids = await user_repo.get_all_user_ids()

    bonus = await settings_repo.get_setting_value("bonus_channel_sub", 1)

    count_ok = 0
    count_unsub = 0

    for uid in user_ids:
        user = await user_repo.get_user(uid)
        if not user or not user.get("sub_my_freelancer_notes", False):
            continue

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
    1-го числа месяца: Топ мемов, награды авторам, сброс счетчика,
    НАГРАДЫ ЗА СНЕЖНУЮ БИТВУ.
    """
    logger.info("Подведение итогов месяца...")
    image_repo = ImageRepo(pool)
    user_repo = UserRepo(pool)
    stats_repo = StatisticsRepo(pool)
    settings_repo = SettingsRepo(pool)

    # --- 1. Динамические настройки ---
    limit = await settings_repo.get_setting_value("limit_top_memes", 10)
    meme_bonus = await settings_repo.get_setting_value("bonus_meme_top_karma_per_meme", 100)

    # Настройки для снежков
    snow_limit = await settings_repo.get_setting_value("snowball_top_limit", 25)
    snow_max = await settings_repo.get_setting_value("snowball_top_max_reward", 1000)
    snow_min = await settings_repo.get_setting_value("snowball_top_min_reward", 100)

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

    # --- 3. Логика наград за ТОП СНЕЖКОВ ---

    if snow_limit > 1:
        step = (snow_max - snow_min) / (snow_limit - 1)
    else:
        step = 0

    snow_leaderboards = {
        "snowball_throws": "☄️ Настойчивость (Броски)",
        "snowball_hits": "🎯 Меткость (Попадания)",
        "snowball_dodges": "💨 Ловкость (Увороты)"
    }

    full_snow_report = ["\n\n---", "<b>❄️ РЕЙТИНГ СНЕЖНОЙ БИТВЫ (НАГРАДЫ)</b>"]

    for sort_col, title in snow_leaderboards.items():
        top_players = await stats_repo.get_top_snowballers(sort_col, limit=snow_limit)

        full_snow_report.append(f"\n🏆 <b>ТОП {snow_limit} ПО {title}</b>")

        for rank, rec in enumerate(top_players, start=1):
            player_id = rec["user_id"]

            raw_reward = snow_max - (rank - 1) * step
            reward = int(round(raw_reward / 10) * 10)

            player_user = await user_repo.get_user(player_id)
            if player_user:
                new_karma = player_user["karma"] + reward
                await user_repo.update_user_profile_parameters(player_id, karma=new_karma)

                player_name = f"@{rec['username']}" if rec['username'] else f"User {player_id}"

                full_snow_report.append(
                    f"   #{rank}. {player_name} ({rec['score']} очков) -> +{reward}✨"
                )

                await safe_send_message(
                    bot, player_id,
                    f"👑 <b>Успешный успех!</b>\n\nВы заняли #{rank} место в рейтинге «{title}» <b>Снежной битвы!</b>\n\nНачислено <b>+{reward}</b> ✨ кармы.",
                    user_repo
                )

    await safe_send_message(bot, bot_settings.LOG_GROUP_ID, "\n".join(full_snow_report))

    # --- 4. Сброс счетчиков ---
    await image_repo.reset_monthly_views()
    logger.info("Счетчики просмотров за месяц сброшены.")

    # 👇 СБРОС СТАТИСТИКИ СНЕЖКОВ
    await stats_repo.reset_snowball_stats()
    logger.info("Счетчики снежной битвы сброшены.")