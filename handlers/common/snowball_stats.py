# handlers/common/snowball_stats.py
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message

from db.db_statistics import StatisticsRepo
from app.services.snowball_service import get_player_stats_text

router = Router()

# Работаем везде: и в ЛС, и в группах
# (фильтр типа чата не ставим, значит принимаем все)

@router.message(Command("snowstats"))
async def snowball_stats_handler(
    message: Message,
    bot: Bot,
    stats_repo: StatisticsRepo
):
    # 1. Определяем, чью статистику смотреть
    if message.reply_to_message:
        # Если ответили на сообщение — берем того юзера
        target_user = message.reply_to_message.from_user
    else:
        # Иначе — свою
        target_user = message.from_user

    # Защита от ботов
    if target_user.is_bot:
        await message.reply("🤖 У ботов нет статистики, мы выше этого.")
        return

    # 2. Получаем имя
    name = target_user.full_name
    # Или юзернейм, если есть
    if target_user.username:
        name = f"@{target_user.username}"

    # 3. Генерируем текст
    text = await get_player_stats_text(target_user.id, name, stats_repo)

    # 4. Отправляем ответом
    await message.reply(text)