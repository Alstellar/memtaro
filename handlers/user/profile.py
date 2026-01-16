# handlers/user/profile.py
from datetime import datetime
from aiogram import Bot, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType

from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo
from db.db_images import ImageRepo
from app.services.safe_sender import safe_send_message
from app.constants import CATEGORIES_MAPPING

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text == "👤 Профиль")
async def show_profile_handler(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        image_repo: ImageRepo
):
    user_id = message.from_user.id
    user = await user_repo.get_user(user_id)

    if not user:
        await safe_send_message(bot, user_id, "Профиль не найден. Напишите /start.")
        return

    # Подгружаем статистику
    stats = await stats_repo.get_statistics_entry(user_id)
    if not stats:
        await stats_repo.add_statistics_entry(user_id)
        stats = await stats_repo.get_statistics_entry(user_id)

    # Формируем данные
    username = user.get("username", "не указан")
    karma = user.get("karma", 0)

    reg_date = user.get("registration_date")
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

    text = (
        "<b>Ваш профиль</b>\n\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Username:</b> @{username}\n"
        f"<b>Регистрация:</b> {reg_str}\n"
        f"<b>Подписка:</b> {prem_str}\n\n"
        f"<b>Тематика мемов:</b> {cat_name}\n\n"
        f"<b>Карма:</b> <b>{karma}</b> ✨\n"
        f"<b>Добавлено мемов:</b> {user_images_count}\n"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Выбор тематики мемов")],
            [KeyboardButton(text="✨ Карма"), KeyboardButton(text="🤝 Реф. система")],
            [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )

    await safe_send_message(
        bot=bot,
        user_id=user_id,
        text=text,
        reply_markup=keyboard,
        user_repo=user_repo
    )