# handlers/user/theme.py
from aiogram import Bot, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo  # Для редиректа в профиль
from db.db_images import ImageRepo  # Для редиректа в профиль

from app.services.safe_sender import safe_send_message
from app.services.user_service import is_user_premium
from app.constants import CATEGORIES_REVERSE_MAPPING
from app.fsm_states import ProfileChoiceState

# Чтобы вернуть пользователя в профиль после смены темы, импортируем функцию
from .profile import show_profile_handler

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text == "🔄 Выбор тематики мемов")
async def change_theme_start(
        message: Message,
        bot: Bot,
        state: FSMContext,
        user_repo: UserRepo
):
    user_id = message.from_user.id

    # Проверка премиума
    if not await is_user_premium(user_id, user_repo):
        sub_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💳 Подписка")],
                [KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )
        await safe_send_message(
            bot=bot,
            user_id=user_id,
            text="Для доступа к выбору тематики требуется активная подписка.",
            reply_markup=sub_kb,
            user_repo=user_repo
        )
        return

    theme_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Общая")],
            [KeyboardButton(text="Животные")],
            [KeyboardButton(text="Кино и сериалы")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )

    await safe_send_message(
        bot=bot,
        user_id=user_id,
        text="<b>Выбор тематики мемов</b>\n\nПожалуйста, выберите одну из тем:",
        reply_markup=theme_kb,
        user_repo=user_repo
    )

    await state.set_state(ProfileChoiceState.waiting_for_theme_choice)


@router.message(ProfileChoiceState.waiting_for_theme_choice)
async def change_theme_process(
        message: Message,
        bot: Bot,
        state: FSMContext,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        image_repo: ImageRepo
):
    choice = message.text.strip()

    if choice == "🏠 Главное меню":
        await state.clear()
        await show_profile_handler(message, bot, user_repo, stats_repo, image_repo)
        return

    if choice not in CATEGORIES_REVERSE_MAPPING:
        await safe_send_message(
            bot=bot,
            user_id=message.chat.id,
            text="Неверный выбор. Используйте кнопки.",
            user_repo=user_repo
        )
        return

    new_cat_id = CATEGORIES_REVERSE_MAPPING[choice]
    await user_repo.update_user_profile_parameters(message.from_user.id, choice_categories=new_cat_id)

    await safe_send_message(
        bot=bot,
        user_id=message.chat.id,
        text=f"Тематика успешно изменена на: <b>{choice}</b>.",
        user_repo=user_repo
    )

    await state.clear()
    await show_profile_handler(message, bot, user_repo, stats_repo, image_repo)