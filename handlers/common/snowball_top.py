# handlers/common/snowball_top.py
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db.db_statistics import StatisticsRepo
from app.services.snowball_service import get_leaderboard_text

router = Router()


# Клавиатура для переключения (создаем функцию, чтобы подсвечивать текущую вкладку, если захотим, но пока простая)
def get_top_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Меткость", callback_data="top_snow:snowball_hits"),
            InlineKeyboardButton(text="💨 Ловкость", callback_data="top_snow:snowball_dodges"),
        ],
        [
            InlineKeyboardButton(text="☄️ Настойчивость", callback_data="top_snow:snowball_throws")
        ]
    ])


@router.message(Command("snowtop"))
async def snowtop_command(message: Message, stats_repo: StatisticsRepo):
    # По умолчанию показываем меткость
    text = await get_leaderboard_text(stats_repo, "snowball_hits")

    await message.answer(text, reply_markup=get_top_keyboard())


@router.callback_query(F.data.startswith("top_snow:"))
async def snowtop_callback(callback: CallbackQuery, stats_repo: StatisticsRepo):
    category = callback.data.split(":")[1]

    # Защита от дурака (валидация категории)
    if category not in ["snowball_hits", "snowball_dodges", "snowball_throws"]:
        await callback.answer("Ошибка категории")
        return

    text = await get_leaderboard_text(stats_repo, category)

    # Пытаемся редактировать. Если текст не изменился (юзер нажал ту же кнопку), aiogram/tg кинет ошибку,
    # которую мы игнорируем (или можно использовать suppress)
    try:
        await callback.message.edit_text(text, reply_markup=get_top_keyboard())
    except Exception:
        pass  # Текст не изменился

    await callback.answer()