# app/services/prediction_service.py
import random
from datetime import date
from loguru import logger
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Наши репозитории
from db.db_users import UserRepo
from db.db_images import ImageRepo
from db.db_predicts import PredictRepo
from db.db_settings import SettingsRepo
from db.db_statistics import StatisticsRepo
from db.db_wisdom_images import WisdomImageRepo
from db.db_bot_images import BotImageRepo
from db.db_chats import ChatRepo

# Наши сервисы и утилиты
from app.services.user_service import is_user_premium, ensure_user_records
from app.services.reward_service import apply_referral_bonus
from app.services.safe_sender import safe_send_photo, safe_send_message, animate_prediction, animate_wisdom

# Контент
from app.keyboards import make_mem_inline_kb, make_wisdom_inline_kb
from app.constants import RETRY_PHRASES


# ====================================================================
# ПРИВАТНЫЙ ЧАТ (process_meme_prediction)
# ====================================================================

async def process_meme_prediction(
        bot: Bot,
        chat_id: int,
        user_id: int,
        via_callback: bool,
        user_repo: UserRepo,
        image_repo: ImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo,
        stats_repo: StatisticsRepo
):
    """
    Логика выдачи Мем-предсказания (Приватный чат).
    """
    # 0. Гарантируем наличие записей
    await ensure_user_records(user_id, predict_repo, stats_repo)

    # 1. Получаем данные
    user = await user_repo.get_user(user_id)
    if not user:
        await safe_send_message(bot, chat_id, "Профиль не найден. Введите /start.", user_repo)
        return

    predicts = await predict_repo.get_predicts(user_id)

    # 👇 Получаем цену повторного мема из БД
    price = await settings_repo.get_setting_value("price_repeat_meme", 5)

    today = date.today()
    last_date = predicts.get("last_predict_date")
    current_id = predicts.get("current_predict_image_id")

    kb = make_mem_inline_kb(price)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    # === СЦЕНАРИЙ 1: Повтор того же мема (бесплатно) ===
    if not via_callback and last_date == today:
        image = await image_repo.get_image(current_id)
        if not image:
            await safe_send_message(bot, chat_id, "Ошибка: прошлый мем не найден.", user_repo)
            return

        # Callback для обновления file_id
        async def update_old_meme_id(new_id: str):
            logger.info(f"Обновляю file_id для image {image['image_id']}")
            await image_repo.update_images_parameters(image_id=image['image_id'], file_id=new_id)

        await safe_send_photo(
            bot=bot, chat_id=chat_id,
            file_id=image.get("file_id"),
            file_path=image.get("file_path"),
            caption=random.choice(RETRY_PHRASES),
            reply_markup=kb,
            user_repo=user_repo,
            update_file_id_callback=update_old_meme_id
        )
        return

    # === СЦЕНАРИЙ 2: Новый мем (платно или первый раз) ===
    deduct_karma = False

    if via_callback and last_date == today:
        if user["karma"] < price:
            await safe_send_message(bot, chat_id, f"Недостаточно кармы ({price}✨) для нового мема.", user_repo)
            return
        deduct_karma = True

    # Выбор категории
    cat_id = user.get("choice_categories", 1)

    async def fetch_random():
        if cat_id == 2: return await image_repo.get_random_image_by_category("category_animals")
        if cat_id == 3: return await image_repo.get_random_image_by_category("category_cinema")
        return await image_repo.get_random_image()

    new_img = None
    for _ in range(10):
        cand = await fetch_random()
        if cand and cand["image_id"] != current_id:
            new_img = cand
            break

    if not new_img:
        new_img = await image_repo.get_random_image()
        if not new_img:
            await safe_send_message(bot, chat_id, "Мемы закончились :(", user_repo)
            return

    # === ОТПРАВКА ===
    caption = f"🔮 Мем-предсказание на сегодня от <a href=\"{ref_link}\">Мем Таро</a>"

    # Callback для обновления file_id (если мем новый локальный)
    async def update_new_meme_id(new_id: str):
        logger.info(f"Сохраняю новый file_id для image {new_img['image_id']}")
        await image_repo.update_images_parameters(image_id=new_img['image_id'], file_id=new_id)

    sent_success = await safe_send_photo(
        bot=bot, chat_id=chat_id,
        file_id=new_img.get("file_id"),
        file_path=new_img.get("file_path"),
        caption=caption,
        reply_markup=kb,
        user_repo=user_repo,
        update_file_id_callback=update_new_meme_id
    )

    if not sent_success:
        return

    # === ОБНОВЛЕНИЕ БД (Начисления) ===
    # Счетчик просмотров картинки
    await image_repo.increment_image_views(new_img["image_id"])

    await predict_repo.update_predicts_parameters(
        user_id=user_id,
        last_predict_date=today,
        current_predict_image_id=new_img["image_id"]
    )

    stats_update = {"count_received_memepredictions": 1}
    is_premium = await is_user_premium(user_id, user_repo)

    if deduct_karma:
        new_karma = user["karma"] - price
        stats_update["spent_karma"] = price
    else:
        # ДИНАМИЧЕСКИЕ НАГРАДЫ (Ежедневный бонус)
        base_bonus = await settings_repo.get_setting_value("bonus_daily_prediction", 1)
        premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

        bonus = base_bonus * premium_mult if is_premium else base_bonus
        new_karma = user["karma"] + bonus

    await user_repo.update_user_profile_parameters(user_id, karma=new_karma)
    await stats_repo.increment_statistics(user_id, **stats_update)

    # ДИНАМИЧЕСКИЙ БОНУС АВТОРУ МЕМА ЗА ПРОСМОТР
    author_id = new_img.get("user_id", 0)
    if author_id and author_id != user_id:
        author_bonus = await settings_repo.get_setting_value("bonus_author_per_view", 1)
        if await is_user_premium(author_id, user_repo):
            author_data = await user_repo.get_user(author_id)
            if author_data:
                # Начисление
                new_karma = author_data["karma"] + author_bonus
                await user_repo.update_user_profile_parameters(author_id, karma=new_karma)

    # ДИНАМИЧЕСКИЙ РЕФЕРАЛЬНЫЙ БОНУС
    ref_base_bonus = await settings_repo.get_setting_value("bonus_ref_prediction", 1)
    await apply_referral_bonus(user_id, user_repo, settings_repo, ref_base_bonus)

    logger.info(f"Mem sent to {user_id}. Img: {new_img['image_id']}. Deduct: {deduct_karma}")


async def process_wisdom_prediction(
        bot: Bot,
        chat_id: int,
        user_id: int,
        via_callback: bool,
        user_repo: UserRepo,
        wisdom_repo: WisdomImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo,
        stats_repo: StatisticsRepo
):
    """
    Логика выдачи Мудрости дня (Приватный чат).
    """
    await ensure_user_records(user_id, predict_repo, stats_repo)
    user = await user_repo.get_user(user_id)
    if not user:
        await safe_send_message(bot, chat_id, "Профиль не найден.", user_repo)
        return

    predicts = await predict_repo.get_predicts(user_id)

    # 👇 Получаем цену повторной мудрости из БД
    price = await settings_repo.get_setting_value("price_repeat_wisdom", 5)

    today = date.today()
    last_date = predicts.get("last_wisdom_date")
    current_id = predicts.get("current_wisdom_image_id")

    kb = make_wisdom_inline_kb(price)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    # === СЦЕНАРИЙ 1: Повтор (бесплатно) ===
    if not via_callback and last_date == today:
        image = await wisdom_repo.get_wisdom_image(current_id)
        if not image:
            await safe_send_message(bot, chat_id, "Мудрость потерялась...", user_repo)
            return

        # Callback для обновления file_id (если локально обновили мудрость)
        async def update_old_wisdom_id(new_id: str):
            logger.info(f"Обновляю file_id для wisdom {image['image_id']}")
            await wisdom_repo.update_wisdom_file_id(image['image_id'], new_id)

        await safe_send_photo(
            bot=bot, chat_id=chat_id,
            file_id=image.get("file_id"),
            file_path=image.get("file_path"),
            caption=f"🧙‍♂️ Мудрость дня от <a href=\"{ref_link}\">Мем Таро</a>",
            reply_markup=kb,
            user_repo=user_repo,
            update_file_id_callback=update_old_wisdom_id
        )
        return

    # === СЦЕНАРИЙ 2: Новая мудрость ===
    deduct_karma = False
    if via_callback and last_date == today:
        if user["karma"] < price:
            await safe_send_message(bot, chat_id, f"Недостаточно кармы ({price}✨).", user_repo)
            return
        deduct_karma = True

    new_img = None
    for _ in range(10):
        cand = await wisdom_repo.get_random_wisdom_image()
        if cand and cand["image_id"] != current_id:
            new_img = cand
            break
    if not new_img:
        await safe_send_message(bot, chat_id, "Мудрости закончились.", user_repo)
        return

    # Callback для новой мудрости
    async def update_new_wisdom_id(new_file_id: str):
        await wisdom_repo.update_wisdom_file_id(new_img['image_id'], new_file_id)

    caption = f"🧙‍♂️ Мудрость дня от <a href=\"{ref_link}\">Мем Таро</a>"

    sent_success = await safe_send_photo(
        bot=bot, chat_id=chat_id,
        file_id=new_img.get("file_id"),
        file_path=new_img.get("file_path"),
        caption=caption,
        reply_markup=kb,
        user_repo=user_repo,
        update_file_id_callback=update_new_wisdom_id
    )

    if not sent_success:
        return

    await predict_repo.update_predicts_parameters(
        user_id=user_id, last_wisdom_date=today, current_wisdom_image_id=new_img["image_id"]
    )

    stats_update = {"count_received_wisdoms": 1}
    is_premium = await is_user_premium(user_id, user_repo)

    if deduct_karma:
        new_karma = user["karma"] - price
        stats_update["spent_karma"] = price
    else:
        # ДИНАМИЧЕСКИЕ НАГРАДЫ (Ежедневный бонус)
        base_bonus = await settings_repo.get_setting_value("bonus_daily_wisdom", 1)
        premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

        bonus = base_bonus * premium_mult if is_premium else base_bonus
        new_karma = user["karma"] + bonus

    await user_repo.update_user_profile_parameters(user_id, karma=new_karma)
    await stats_repo.increment_statistics(user_id, **stats_update)

    # ДИНАМИЧЕСКИЙ РЕФЕРАЛЬНЫЙ БОНУС
    ref_base_bonus = await settings_repo.get_setting_value("bonus_ref_wisdom", 1)
    await apply_referral_bonus(user_id, user_repo, settings_repo, ref_base_bonus)

    logger.info(f"Wisdom sent to {user_id}. Deduct: {deduct_karma}")


# ====================================================================
# ГРУППОВОЙ ЧАТ (process_group_meme)
# ====================================================================

async def process_group_meme(
        bot: Bot,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        via_callback: bool,
        user_repo: UserRepo,
        image_repo: ImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo,
        stats_repo: StatisticsRepo,
        bot_image_repo: BotImageRepo,
        chat_repo: ChatRepo,
        chat_title: str,
        chat_username: str = None
):
    # 1. Регистрируем группу
    await chat_repo.register_chat(chat_id, chat_title, chat_username)

    # 2. Проверяем пользователя
    user = await user_repo.get_user(user_id)
    bot_info = await bot.get_me()

    # Кнопка регистрации / перехода в ЛС
    start_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Зарегистрироваться в Мем Таро 🔮",
                              url=f"https://t.me/{bot_info.username}?start=ref_group")]
    ])

    # Если юзера нет в базе -> предлагаем регистрацию
    if not user:
        # Пытаемся найти картинку "need_click_start"
        err_img = await bot_image_repo.get_bot_image_for_layout("BOT_IMAGES", "need_click_start")
        file_id = err_img.get("file_id") if err_img else None

        await safe_send_photo(
            bot=bot, chat_id=chat_id,
            file_id=file_id, file_path=err_img.get("image") if err_img else None,
            caption="Чтобы получить предсказание, нужно зарегистрироваться в боте! 👇",
            reply_markup=start_kb,
            reply_to_message_id=reply_to_message_id
        )
        return

    # 3. Проверяем лимиты
    await ensure_user_records(user_id, predict_repo, stats_repo)
    predicts = await predict_repo.get_predicts(user_id)

    today = date.today()
    last_date = predicts.get("last_predict_date")
    current_id = predicts.get("current_predict_image_id")

    # 👇 Получаем цену повторного мема из БД
    price = await settings_repo.get_setting_value("price_repeat_meme", 5)

    # Кнопка платного повтора
    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Новый мем за {price}✨", callback_data="new_mem_group")]
    ])

    # === СЦЕНАРИЙ 1: Повтор (бесплатно) ===
    if not via_callback and last_date == today:
        image = await image_repo.get_image(current_id)
        if image:
            await safe_send_photo(
                bot=bot, chat_id=chat_id,
                file_id=image.get("file_id"), file_path=image.get("file_path"),
                caption=random.choice(RETRY_PHRASES),
                reply_markup=repeat_kb,
                reply_to_message_id=reply_to_message_id
            )
        return

    # === СЦЕНАРИЙ 2: Новый мем ===
    deduct_karma = False

    # Если это колбэк и сегодня уже было -> Платно
    if via_callback and last_date == today:
        if user["karma"] < price:
            # Картинка "мало кармы"
            err_img = await bot_image_repo.get_bot_image_for_layout("BOT_IMAGES", "need_up_karma")
            file_id = err_img.get("file_id") if err_img else None

            await safe_send_photo(
                bot=bot, chat_id=chat_id,
                file_id=file_id, file_path=err_img.get("image") if err_img else None,
                caption=f"Недостаточно кармы ({price}✨).",
                reply_markup=start_kb,
                reply_to_message_id=reply_to_message_id
            )
            return
        deduct_karma = True

    # Ищем мем
    new_img = None
    # (Тут простая логика: в группах всегда общая категория для простоты, или можно брать из профиля юзера)
    for _ in range(10):
        cand = await image_repo.get_random_image()
        if cand and cand["image_id"] != current_id:
            new_img = cand
            break
    if not new_img:
        return  # Тихо выходим, если беда

    # Отправка
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    caption = f"🔮 Мем-предсказание от <a href=\"{ref_link}\">Мем Таро</a>"

    # Колбэк для обновления ID локального мема
    async def update_new_meme_id(new_id: str):
        await image_repo.update_images_parameters(image_id=new_img['image_id'], file_id=new_id)

    sent = await safe_send_photo(
        bot=bot, chat_id=chat_id,
        file_id=new_img.get("file_id"), file_path=new_img.get("file_path"),
        caption=caption, reply_markup=repeat_kb,
        reply_to_message_id=reply_to_message_id,
        update_file_id_callback=update_new_meme_id
    )

    if not sent: return

    # Обновляем БД
    await image_repo.increment_image_views(new_img["image_id"])

    await predict_repo.update_predicts_parameters(
        user_id=user_id, last_predict_date=today, current_predict_image_id=new_img["image_id"]
    )

    stats_update = {"count_received_memepredictions": 1}
    is_premium = await is_user_premium(user_id, user_repo)

    if deduct_karma:
        new_karma = user["karma"] - price
        stats_update["spent_karma"] = price
    else:
        # ДИНАМИЧЕСКИЕ НАГРАДЫ (Ежедневный бонус)
        base_bonus = await settings_repo.get_setting_value("bonus_daily_prediction", 1)
        premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

        bonus = base_bonus * premium_mult if is_premium else base_bonus
        new_karma = user["karma"] + bonus

    await user_repo.update_user_profile_parameters(user_id, karma=new_karma)
    await stats_repo.increment_statistics(user_id, **stats_update)

    # Бонус автору (если есть)
    author_id = new_img.get("user_id", 0)
    if author_id and author_id != user_id:
        author_bonus = await settings_repo.get_setting_value("bonus_author_per_view", 1)
        if await is_user_premium(author_id, user_repo):
            author_data = await user_repo.get_user(author_id)
            if author_data:
                # Начисление
                new_karma = author_data["karma"] + author_bonus
                await user_repo.update_user_profile_parameters(author_id, karma=new_karma)


# ====================================================================
# ГРУППОВОЙ ЧАТ (process_group_wisdom) - ВОССТАНОВЛЕН
# ====================================================================

async def process_group_wisdom(
        bot: Bot,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        via_callback: bool,
        user_repo: UserRepo,
        wisdom_repo: WisdomImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo, # 👈 Добавлен аргумент
        stats_repo: StatisticsRepo,
        bot_image_repo: BotImageRepo,
        chat_repo: ChatRepo,
        chat_title: str,
        chat_username: str = None
):
    await chat_repo.register_chat(chat_id, chat_title, chat_username)
    user = await user_repo.get_user(user_id)
    bot_info = await bot.get_me()

    start_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Мем Таро 🔮", url=f"https://t.me/{bot_info.username}")]
    ])

    if not user:
        err_img = await bot_image_repo.get_bot_image_for_layout("BOT_IMAGES", "need_click_start")
        file_id = err_img.get("file_id") if err_img else None
        await safe_send_photo(
            bot=bot, chat_id=chat_id,
            file_id=file_id, file_path=err_img.get("image") if err_img else None,
            caption="Новая мудрость доступна после регистрации! 👇",
            reply_markup=start_kb,
            reply_to_message_id=reply_to_message_id
        )
        return

    await ensure_user_records(user_id, predict_repo, stats_repo)
    predicts = await predict_repo.get_predicts(user_id)

    today = date.today()
    last_date = predicts.get("last_wisdom_date")
    current_id = predicts.get("current_wisdom_image_id")

    # 👇 Получаем цену повторной мудрости из БД
    price = await settings_repo.get_setting_value("price_repeat_wisdom", 5)

    repeat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Новая мудрость за {price}✨", callback_data="new_wisdom_group")]
    ])

    # Сценарий 1: Повтор
    if not via_callback and last_date == today:
        image = await wisdom_repo.get_wisdom_image(current_id)
        if image:
            ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
            await safe_send_photo(
                bot=bot, chat_id=chat_id,
                file_id=image.get("file_id"), file_path=image.get("file_path"),
                caption=f"🧙‍♂️ Мудрость дня от <a href=\"{ref_link}\">Мем Таро</a>",
                reply_markup=repeat_kb,
                reply_to_message_id=reply_to_message_id
            )
        return

    # Сценарий 2: Новая
    deduct_karma = False
    if via_callback and last_date == today:
        if user["karma"] < price:
            err_img = await bot_image_repo.get_bot_image_for_layout("BOT_IMAGES", "need_up_karma")
            file_id = err_img.get("file_id") if err_img else None
            await safe_send_photo(
                bot=bot, chat_id=chat_id,
                file_id=file_id, file_path=err_img.get("image") if err_img else None,
                caption=f"Недостаточно кармы ({price}✨).",
                reply_markup=start_kb,
                reply_to_message_id=reply_to_message_id
            )
            return
        deduct_karma = True

    new_img = None
    for _ in range(10):
        cand = await wisdom_repo.get_random_wisdom_image()
        if cand and cand["image_id"] != current_id:
            new_img = cand
            break
    if not new_img: return

    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    caption = f"🧙‍♂️ Мудрость дня от <a href=\"{ref_link}\">Мем Таро</a>"

    async def update_new_wisdom_id(new_id: str):
        await wisdom_repo.update_wisdom_file_id(new_img['image_id'], new_id)

    sent = await safe_send_photo(
        bot=bot, chat_id=chat_id,
        file_id=new_img.get("file_id"), file_path=new_img.get("file_path"),
        caption=caption, reply_markup=repeat_kb,
        reply_to_message_id=reply_to_message_id,
        update_file_id_callback=update_new_wisdom_id
    )

    if not sent: return

    await predict_repo.update_predicts_parameters(
        user_id=user_id, last_wisdom_date=today, current_wisdom_image_id=new_img["image_id"]
    )

    stats_update = {"count_received_wisdoms": 1}
    is_premium = await is_user_premium(user_id, user_repo)

    if deduct_karma:
        new_karma = user["karma"] - price
        stats_update["spent_karma"] = price
    else:
        base_bonus = await settings_repo.get_setting_value("bonus_daily_wisdom", 1)
        premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

        bonus = base_bonus * premium_mult if is_premium else base_bonus
        new_karma = user["karma"] + bonus

    await user_repo.update_user_profile_parameters(user_id, karma=new_karma)
    await stats_repo.increment_statistics(user_id, **stats_update)

    ref_base_bonus = await settings_repo.get_setting_value("bonus_ref_wisdom", 1)
    await apply_referral_bonus(user_id, user_repo, settings_repo, ref_base_bonus)