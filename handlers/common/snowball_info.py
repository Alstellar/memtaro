# handlers/common/snowball_info.py
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from db.db_settings import SettingsRepo # 👈 Добавлен импорт для цены
from db.db_users import UserRepo # 👈 Добавлен импорт для safe_sender
from app.services.safe_sender import safe_send_message

router = Router()


@router.message(Command("snow_info"))
async def snow_info_handler(
    message: Message,
    bot: Bot, # 👈 Добавлен аргумент
    settings_repo: SettingsRepo, # 👈 Добавлен аргумент
    user_repo: UserRepo # 👈 Добавлен аргумент
):
    # 1. Получаем динамическую цену броска
    price = await settings_repo.get_setting_value("price_snowball_throw", 5)

    text = (
        "❄️ <b>Большая Снежная Битва</b> ❄️\n\n"
        "Добро пожаловать на ледяную арену! Здесь вы можете закидать друзей снежками, "
        "прокачать меткость и попасть в топ лучших игроков!\n\n"

        "🎮 <b>Как играть?</b>\n"
        "В групповом чате выберите сообщение «жертвы» и <b>ответьте</b> на него:\n"
        "• Командой <code>/snowball</code>\n"
        "• Или просто словом <b>Снежок</b> / смайлом ❄️\n\n"

        f"💸 <b>Экономика:</b>\n"
        f"Один бросок стоит <b>{price} ✨ кармы</b>. Списывается сразу.\n\n"

        "🎲 <b>Механика (Рандом):</b>\n"
        "Ваш бросок имеет 50% шанс на успех и **четыре** возможных исхода:\n"
        "• <b>Крит. Попадание (5%)</b> 🔥 — Награда кармой (от 50✨) и +3 к Меткости!\n"
        "• <b>Обычное Попадание (45%)</b> 🎯 — Просто +1 к Меткости.\n"
        "• <b>Уворот (45%)</b> 💨 — Соперник получает +1 к Ловкости.\n"
        "• <b>Крит. Промах (5%)</b> 🤡 — Вы поскользнулись. Смех и позор, очков нет.\n\n"

        "📊 <b>Полезные команды:</b>\n"
        "• <code>/snowstats</code> — Ваша статистика (звание, точность).\n"
        "• <code>/snowstats</code> (в ответ другому) — Посмотреть статистику друга.\n"
        "• <code>/snowtop</code> — Глобальный рейтинг лучших игроков.\n"
        "• ❄️ (Кнопка) — Бросить в ответ!\n\n"
        "<i>Готовы? Целься... Пли!</i>"
    )

    # Используем безопасную отправку, так как теперь у нас есть все зависимости
    await safe_send_message(
        bot=bot,
        user_id=message.chat.id,
        text=text,
        user_repo=user_repo,
        reply_markup=None
    )