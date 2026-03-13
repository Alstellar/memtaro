# handlers/user/profile.py
from datetime import datetime
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType

from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo
from db.db_images import ImageRepo
from app.services.safe_sender import safe_send_message
from app.services.user_service import get_profile_service
from app.constants import CATEGORIES_MAPPING, PROFILE_TEXT_PRIVATE, PROFILE_TEXT_GROUP

router = Router()


@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def show_profile_handler(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        image_repo: ImageRepo
):
    # Определяем тип чата
    chat_type = message.chat.type

    # Получаем ProfileService
    profile_service = get_profile_service(user_repo, stats_repo)

    # Обновляем активность пользователя
    user_id = message.from_user.id
    await profile_service.update_user_activity(user_id)

    # Обновляем юзернейм, если он изменился
    username = message.from_user.username
    if username:
        current_user = await user_repo.get_user(user_id)
        if current_user and current_user.get("username") != username:
            await user_repo.update_user_profile_parameters(user_id, username=username)

    # Если это групповой чат или команда вызвана с упоминанием, показываем профиль другого пользователя
    target_user_id = user_id  # по умолчанию показываем профиль текущего пользователя

    # Проверяем, есть ли упоминание другого пользователя
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_user_id = target_user.id
    elif message.entities and len(message.entities) > 0:
        # Пытаемся извлечь юзернейм из текста сообщения
        text = message.text
        entities = message.entities

        for entity in entities:
            if entity.type == "mention":
                # Обработка упоминания в формате "@username"
                username_mention = text[entity.offset:entity.offset + entity.length]
                username = username_mention[1:]  # убираем символ @

                # Ищем пользователя по юзернейму
                mentioned_user = await user_repo.get_user_by_username(username)
                if mentioned_user:
                    target_user_id = mentioned_user['user_id']
                break
            elif entity.type == "text_mention":
                # Обработка упоминания в формате "[username](tg://user?id=123456789)"
                target_user = entity.user
                target_user_id = target_user.id
                break

    # Если нашли целевого пользователя, показываем его профиль
    if target_user_id != user_id:
        user_id = target_user_id
        user = await user_repo.get_user(user_id)

        if not user:
            await safe_send_message(bot, message.chat.id, "Пользователь с таким профилем не найден.")
            return

    user = await user_repo.get_user(user_id)

    if not user:
        await safe_send_message(bot, user_id, "Профиль не найден. Напишите /start.")
        return

    # Подгружаем статистику
    stats = await stats_repo.get_statistics_entry(user_id)
    if not stats:
        await stats_repo.add_statistics_entry(user_id)
        stats = await stats_repo.get_statistics_entry(user_id)

    # Получаем данные профиля через ProfileService
    profile_data = await profile_service.get_user_profile_data(user_id)

    if not profile_data:
        await safe_send_message(bot, user_id, "Не удалось загрузить данные профиля.")
        return

    # Формируем данные
    username = profile_data.get("username", "не указан")
    karma = profile_data.get("karma", 0)
    activity_level = profile_data.get("activity_level", 0)
    rank = profile_data.get("rank", "Новичок")
    external_activity_score = profile_data.get("external_activity_score", 0)
    internal_activity_count = profile_data.get("internal_activity_count", 0)
    external_activity_count = profile_data.get("external_activity_count", 0)

    reg_date = profile_data.get("registration_date")
    reg_str = reg_date.strftime("%d.%m.%Y") if reg_date else "не указана"

    prem_date = user.get("premium_date")
    now = datetime.now()
    if prem_date and prem_date >= now:
        prem_str = prem_date.strftime("%d.%m.%Y")
    else:
        prem_str = "нет подписки"

    cat_code = user.get("choice_categories", 1)
    cat_name = CATEGORIES_MAPPING.get(cat_code, "Общая")

    user_images_count = await image_repo.get_images_statistics_by_user_id(user_id)

    # Формируем текст профиля в зависимости от типа чата
    if chat_type == ChatType.PRIVATE:
        # Для частного чата показываем полный профиль
        text = PROFILE_TEXT_PRIVATE.format(
            user_id=user_id,
            username=username,
            registration_date=reg_str,
            premium_status=prem_str,
            category=cat_name,
            karma=karma,
            memes_count=user_images_count,
            activity_level=activity_level,
            rank=rank,
            external_activity_score=external_activity_score,
            internal_activity_count=internal_activity_count,
            external_activity_count=external_activity_count
        )
    else:
        # Для группового чата показываем сокращенный профиль
        text = PROFILE_TEXT_GROUP.format(
            user_id=user_id,
            username=username,
            karma=karma,
            rank=rank,
            activity_level=activity_level
        )

    # Если это частный чат, показываем полную клавиатуру
    if chat_type == ChatType.PRIVATE:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔄 Выбор тематики мемов")],
                [KeyboardButton(text="✨ Карма"), KeyboardButton(text="🤝 Реф. система")],
                [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="📊 Статистика")],
                [KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )
    else:
        # В групповом чате показываем только кнопку главного меню
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )

    await safe_send_message(
        bot=bot,
        user_id=message.chat.id,  # Отправляем в тот же чат, где была вызвана команда
        text=text,
        reply_markup=keyboard,
        user_repo=user_repo
    )