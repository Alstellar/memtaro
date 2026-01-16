# app/services/snowball_service.py
import random
from loguru import logger
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Union, Optional

from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo, SortField
from db.db_settings import SettingsRepo
from db.db_activity import ActivityRepo
from app.services.safe_sender import safe_send_message, fetch_user_display_data
from app.services.user_service import is_user_premium
from app.constants import SNOWBALL_HITS, SNOWBALL_MISSES, SNOWBALL_CRIT_HITS, SNOWBALL_CRIT_MISSES


# ================= ОСНОВНАЯ ЛОГИКА (ЦЕНТРАЛЬНОЕ ДЕЙСТВИЕ) =================

async def execute_snowball_action(
        sender_id: int,
        target_id: int,
        chat_id: int,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo,
        activity_repo: ActivityRepo,
        source_object: Union[Message, CallbackQuery]
):
    """
    Центральная функция для выполнения броска снежком.
    """

    # 1. Получаем все необходимые динамические настройки
    price = await settings_repo.get_setting_value("price_snowball_throw", 5)
    bonus_crit = await settings_repo.get_setting_value("bonus_crit_hit", 50)
    premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)
    min_users = await settings_repo.get_setting_value("min_active_users_for_random", 10)

    # Преобразование вероятностей (из % в float 0.0-1.0)
    prob_crit_miss = await settings_repo.get_setting_value("prob_crit_miss", 5) / 100
    prob_hit_base = await settings_repo.get_setting_value("prob_hit_base", 50) / 100
    prob_crit_hit = await settings_repo.get_setting_value("prob_crit_hit", 5) / 100

    # 2. Получаем данные отправителя и цели из БД и API
    sender_user = await user_repo.get_user(sender_id)
    target_user_data = await user_repo.get_user(target_id)

    if not sender_user:
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            link = f'<a href="https://t.me/{bot_username}">Мем Таро</a>'
        except Exception:
            # Fallback, если не удается получить данные о боте
            link = ""

        error_text = (
            "Что-то я вас не припоминаю 🤔\n\n"
            f"⚠️ Чтобы кидать снежки в других игроков, нужно зарегистрироваться в боте {link}!"
        )

        await safe_send_message(bot=bot, user_id=chat_id, text=error_text, user_repo=user_repo)
        return

    # Корректное получение имени и ссылки (через fetch_user_display_data)
    sender_name, sender_link = await fetch_user_display_data(bot, sender_id, sender_user)
    target_name, target_link = await fetch_user_display_data(bot, target_id, target_user_data)

    if target_user_data:
        # Цель зарегистрирована, используем данные из БД
        target_name, target_link = await fetch_user_display_data(bot, target_id, target_user_data)
        is_target_registered = True
    else:
        # Цель НЕ зарегистрирована. Получаем имя напрямую из API
        target_name, target_link = await fetch_user_display_data(bot, target_id, {'username': None})
        is_target_registered = False

    # 3. Проверка баланса и списание кармы
    current_karma = sender_user.get("karma", 0)
    if current_karma < price:
        # 🛑 ИСПРАВЛЕНИЕ 1: Ошибка -> REPLAY. Отвечаем на исходное сообщение/колбэк
        await safe_send_message(
            bot=bot,
            user_id=chat_id,
            text=f"@{sender_name}, недостаточно кармы ({price}✨) для броска!",
            user_repo=user_repo,
            # Отвечаем на команду (Message) или на кнопку (CallbackQuery.message.message_id)
            reply_to_message_id=source_object.message_id if isinstance(source_object, Message) else source_object.message.message_id,
        )
        return

    new_karma = current_karma - price
    await user_repo.update_user_profile_parameters(sender_id, karma=new_karma)

    # Общая статистика: потраченная карма и +1 к попыткам броска
    await stats_repo.increment_statistics(sender_id, spent_karma=price, snowball_throws=1)

    # 4. RNG и Расчет результата
    roll = random.random()

    result_text = ""

    # --- СЦЕНАРИЙ 1: Критический промах (prob_crit_miss) ---
    if roll < prob_crit_miss:
        phrase = random.choice(SNOWBALL_CRIT_MISSES)
        result_text = (
            f"🤡 <b>{sender_link}</b> пытался кинуть снежок, но...\n\n"
            f"<i>{phrase}</i>"
        )

    # --- СЦЕНАРИЙ 2: Промах / Уворот (45%) ---
    elif prob_crit_miss <= roll < prob_hit_base:
        if is_target_registered:  # 🛑 Начисляем только если цель зарегистрирована
            await stats_repo.increment_statistics(target_id, snowball_dodges=1)
            target_stats_msg = f"🛡 <b>{target_name}</b> получает +1 к рейтингу Ловкости!"
        else:
            target_stats_msg = f"🛡 {target_name} увернулся, но не получил очков рейтинга."

        phrase = random.choice(SNOWBALL_MISSES)
        result_text = (
            f"💨 <b>{sender_link}</b> метнул снежок в <b>{target_link}</b>...\n\n"
            f"<i>{phrase}</i>\n\n"
            f"{target_stats_msg}"
        )

    # --- СЦЕНАРИЙ 3: Попадание (45%) ---
    elif prob_hit_base <= roll < (1.0 - prob_crit_hit):
        await stats_repo.increment_statistics(sender_id, snowball_hits=1)
        phrase = random.choice(SNOWBALL_HITS)
        result_text = (
            f"👊 <b>{sender_link}</b> попал в <b>{target_link}</b>!\n\n"
            f"<i>{phrase}</i>\n\n"
            f"🎯 <b>{sender_name}</b> получает +1 к Меткости!"
        )

    # --- СЦЕНАРИЙ 4: Критическое попадание (5%) ---
    else:
        is_premium = await is_user_premium(sender_id, user_repo)
        bonus_to_add = bonus_crit * premium_mult if is_premium else bonus_crit

        # Начисление
        final_karma_payout = new_karma + bonus_to_add
        await user_repo.update_user_profile_parameters(sender_id, karma=final_karma_payout)
        await stats_repo.increment_statistics(sender_id, snowball_hits=3)  # +3 к меткости

        phrase = random.choice(SNOWBALL_CRIT_HITS)
        result_text = (
            f"🔥 <b>{sender_link}</b> УЛЬТАНУЛ <b>{target_link}</b>!\n"
            f"<i>{phrase}</i>\n\n"
            f"🎯 Атакующий получает +3 к Меткости и <b>+{bonus_to_add}</b> ✨!"
        )

    # 5. КЛАВИАТУРА И АКТИВНОСТЬ ГРУППЫ

    kb_buttons = [
        InlineKeyboardButton(
            text="❄️ Бросить в ответ!",
            callback_data=f"snow_reply:{target_id}:{sender_id}"
        ),
    ]

    active_users_count = await activity_repo.get_active_user_count(chat_id, days=30)

    if active_users_count >= min_users:
        kb_buttons.append(
            InlineKeyboardButton(
                text="🎲 Случайный бросок",
                callback_data=f"snow_rand:{chat_id}:{sender_id}"  # Передаем chat_id и ID отправителя (для исключения)
            )
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[kb_buttons])

    # 6. Отправка сообщения
    await safe_send_message(bot=bot, user_id=chat_id, text=result_text, user_repo=user_repo, reply_markup=kb)

    logger.info(f"Snowball: Sender {sender_id} -> Target {target_id} in chat {chat_id}.")


# ================= ВХОДНЫЕ ТОЧКИ (УПРОЩЕННЫЕ) =================

async def process_snowball_throw(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo,
        activity_repo: ActivityRepo
):
    """ Обработка броска по команде /snowball или ответом. """

    chat_id = message.chat.id
    sender_id = message.from_user.id

    if not message.reply_to_message:
        await safe_send_message(bot=bot, user_id=chat_id, text="Чтобы кинуть снежок, ответьте на сообщение пользователя!",
                                user_repo=user_repo, reply_to_message_id=message.message_id)
        return

    target_id = message.reply_to_message.from_user.id

    if sender_id == target_id:
        await safe_send_message(bot=bot, user_id=chat_id, text="Вы не можете кинуть снежок в себя.",
                                user_repo=user_repo, reply_to_message_id=message.message_id)
        return

    if target_id == bot.id:
        # 🛑 ИСПРАВЛЕНИЕ 6: Бросок в бота -> REPLAY на команду
        await safe_send_message(bot=bot, user_id=chat_id, text="Не стоит кидать снежки в меня! 😠",
                                user_repo=user_repo, reply_to_message_id=message.message_id)
        return

    # Запускаем основное действие
    await execute_snowball_action(sender_id=sender_id, target_id=target_id, chat_id=chat_id, bot=bot,
                                  user_repo=user_repo, stats_repo=stats_repo, settings_repo=settings_repo,
                                  activity_repo=activity_repo, source_object=message)


async def process_random_throw(
        callback: CallbackQuery,
        chat_id: int,
        sender_id: int,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo,
        activity_repo: ActivityRepo
):
    """ Обработка броска по кнопке "Случайный бросок". """
    await callback.answer("Выбираем случайную цель...")

    # 1. Получаем ID случайной жертвы (30 дней активности, исключая отправителя)
    target_id = await activity_repo.get_random_active_user(chat_id, sender_id, days=30)

    if not target_id:
        # 🛑 ИСПРАВЛЕНИЕ 7: No Target Error -> REPLAY на сообщение с кнопкой
        await safe_send_message(bot=bot, user_id=chat_id, text="К сожалению, активных целей для броска не найдено!",
                                user_repo=user_repo, reply_to_message_id=callback.message.message_id)
        return

    # 2. Запускаем основное действие
    await execute_snowball_action(sender_id=sender_id, target_id=target_id, chat_id=chat_id, bot=bot,
                                  user_repo=user_repo, stats_repo=stats_repo, settings_repo=settings_repo,
                                  activity_repo=activity_repo, source_object=callback)

async def process_retaliation_throw(
        callback: CallbackQuery,
        new_sender_id: int,
        new_target_id: int,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo,
        activity_repo: ActivityRepo
):
    """ Обработка броска по кнопке "Бросить в ответ". """
    await callback.answer()

    # Запускаем основное действие
    await execute_snowball_action(sender_id=new_sender_id, target_id=new_target_id, chat_id=callback.message.chat.id,
                                  bot=bot, user_repo=user_repo, stats_repo=stats_repo, settings_repo=settings_repo,
                                  activity_repo=activity_repo, source_object=callback)



async def get_player_stats_text(
        user_id: int,
        name: str,
        stats_repo: StatisticsRepo
):
    """
    Генерирует текст статистики игрока для команды /snowstats.
    """
    stats = await stats_repo.get_statistics_entry(user_id)

    # Если записей нет, считаем по нулям
    throws = stats.get("snowball_throws", 0) if stats else 0
    hits = stats.get("snowball_hits", 0) if stats else 0
    dodges = stats.get("snowball_dodges", 0) if stats else 0

    # Считаем точность
    accuracy = (hits / throws * 100) if throws > 0 else 0.0

    # Выдаем звания на основе попаданий
    title = "Новичок ❄️"
    if hits > 5: title = "Любитель ☃️"
    if hits > 20: title = "Опытный боец 🌨"
    if hits > 50: title = "Снайпер 🎯"
    if hits > 100: title = "Ледяной Жнец ☠️"
    if hits > 500: title = "Йети 🦍"

    text = (
        f"📊 <b>Статистика игрока {name}</b>\n\n"
        f"🎖 Звание: <b>{title}</b>\n\n"
        f"☄️ Бросков: <b>{throws}</b>\n"
        f"🎯 Попаданий: <b>{hits}</b>\n"
        f"💨 Уворотов: <b>{dodges}</b>\n"
        f"📐 Точность: <b>{accuracy:.1f}%</b>"
    )

    return text


async def get_leaderboard_text(
        stats_repo: StatisticsRepo,
        category: SortField
):
    """
    Формирует текст топа для команды /snowtop.
    """
    # Заголовки
    titles = {
        "snowball_hits": "🎯 Топ Снайперов (Попадания)",
        "snowball_dodges": "💨 Топ Нео (Увороты)",
        "snowball_throws": "☄️ Топ Маньяков (Броски)"
    }

    title = titles.get(category, "Топ")
    # Используем лимит 25, который мы определили ранее
    records = await stats_repo.get_top_snowballers(category, limit=25)

    if not records:
        return f"<b>{title}</b>\n\nПока никто не отличился. Будь первым!"

    lines = [f"<b>{title}</b>\n"]

    for idx, rec in enumerate(records, start=1):
        score = rec["score"]
        user_id = rec["user_id"]
        # Если есть юзернейм - используем его, иначе ID
        name = f"@{rec['username']}" if rec['username'] else f"User {user_id}"

        # Медали для топ-3
        medal = ""
        if idx == 1:
            medal = "🥇 "
        elif idx == 2:
            medal = "🥈 "
        elif idx == 3:
            medal = "🥉 "

        lines.append(f"{idx}. {medal}<b>{name}</b> — {score}")

    return "\n".join(lines)