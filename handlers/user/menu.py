# handlers/user/menu.py
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatType

from app.config import BotSettings
from app.keyboards import get_main_menu_keyboard, kb_menu
from app.constants import INFO_TEXT_PRIVATE, AGREEMENT_TEXT, PROJECTS_TEXT

# 👇 Импортируем наш безопасный сендер и репозиторий
from app.services.safe_sender import safe_send_message
from db.db_users import UserRepo

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


# --- Главное меню ---
@router.message(Command("menu"))
@router.message(F.text == "🏠 Главное меню")
async def main_menu_handler(
        message: Message,
        bot: Bot,
        bot_settings: BotSettings,
        user_repo: UserRepo
):
    """
    Открывает главное меню.
    """
    is_admin = message.from_user.id in bot_settings.ADMIN_IDS
    keyboard = get_main_menu_keyboard(is_admin)

    await safe_send_message(
        bot=bot,
        user_id=message.chat.id,
        text="<b>Главное меню</b>\n\nВыберите нужную опцию:",
        user_repo=user_repo,
        reply_markup=keyboard
    )


# --- Инфо ---
@router.message(Command("info"))
@router.message(F.text == "ℹ️ Инфо")
async def info_handler(message: Message, bot: Bot, user_repo: UserRepo):
    await safe_send_message(
        bot=bot,
        user_id=message.chat.id,
        text=INFO_TEXT_PRIVATE,
        user_repo=user_repo
    )


# --- Пользовательское соглашение ---
@router.message(F.text == "📜 Пользовательское соглашение")
async def agreement_handler(message: Message, bot: Bot, user_repo: UserRepo):
    await safe_send_message(
        bot=bot,
        user_id=message.chat.id,
        text=AGREEMENT_TEXT,
        user_repo=user_repo,
        reply_markup=kb_menu()
    )


# --- Наши проекты ---
@router.message(F.text == "📌 Наши проекты")
async def projects_handler(message: Message, bot: Bot, user_repo: UserRepo):
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✔️ Подписаться на канал", url="https://t.me/my_freelancer_notes")]
    ])

    await safe_send_message(
        bot=bot,
        user_id=message.chat.id,
        text=PROJECTS_TEXT,
        user_repo=user_repo,
        reply_markup=inline_kb
    )