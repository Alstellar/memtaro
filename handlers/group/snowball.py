# handlers/group/snowball.py
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo
from db.db_settings import SettingsRepo
from db.db_activity import ActivityRepo

from app.services.snowball_service import process_snowball_throw, process_retaliation_throw, process_random_throw

router = Router()
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
router.callback_query.filter(F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))



async def snowball_handler(message: Message, bot: Bot, user_repo: UserRepo, stats_repo: StatisticsRepo,
                           settings_repo: SettingsRepo, activity_repo: ActivityRepo):

    await process_snowball_throw(message=message, bot=bot, user_repo=user_repo, stats_repo=stats_repo,
                                 settings_repo=settings_repo, activity_repo=activity_repo)


@router.callback_query(F.data.startswith("snow_reply:"))
async def snowball_retaliation_callback(callback: CallbackQuery, bot: Bot, user_repo: UserRepo, stats_repo: StatisticsRepo,
                                        settings_repo: SettingsRepo, activity_repo: ActivityRepo):
    # callback.data: snow_reply:<OriginalTarget_ID>:<OriginalSender_ID>

    # 1. Парсим ID
    try:
        _, original_target_id_str, original_sender_id_str = callback.data.split(":")
        # Исходный агрессор становится новой жертвой
        new_target_id = int(original_sender_id_str)
    except ValueError:
        await callback.answer("Ошибка данных.")
        return

    # 🛑 НОВАЯ ЛОГИКА:
    # Отправитель (новый) - это тот, кто нажал кнопку.
    new_sender_id = callback.from_user.id

    # Проверка на бросок в себя (если агрессор сам нажал кнопку)
    if new_sender_id == new_target_id:
        await callback.answer("Нельзя бросать в себя!\n\nОтветьте ❄️ игроку, в которого хотите бросить снежок", show_alert=True)
        return

    # Вызываем логику ответного броска
    await process_retaliation_throw( callback=callback, new_sender_id=new_sender_id,  new_target_id=new_target_id,
                                     bot=bot, user_repo=user_repo, stats_repo=stats_repo,
                                     settings_repo=settings_repo, activity_repo=activity_repo)


@router.callback_query(F.data.startswith("snow_rand:"))
async def snowball_random_callback(
        callback: CallbackQuery,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo,
        activity_repo: ActivityRepo
):
    """
    Обрабатывает нажатие кнопки "Случайный бросок".
    callback.data: snow_rand:<chat_id>:<sender_id>
    """
    try:
        _, chat_id_str, original_sender_id_str = callback.data.split(":")
        chat_id = int(chat_id_str)

        # 🛑 ИСПРАВЛЕНИЕ: Отправитель — тот, кто нажал кнопку, а не тот, кто в данных
        sender_id = callback.from_user.id

        # Оставляем эту проверку, чтобы нельзя было активировать старую кнопку,
        # созданную для другого пользователя (хотя бы по ID).
        if callback.from_user.id != int(original_sender_id_str):
            await callback.answer("Эта кнопка была создана для другого пользователя. Воспользуйтесь /snowball.")
            return

    except ValueError:
        await callback.answer("Ошибка данных.")
        return

    # Вызываем логику случайного броска
    await process_random_throw(callback=callback, chat_id=chat_id, sender_id=sender_id, bot=bot,
                               user_repo=user_repo, stats_repo=stats_repo, settings_repo=settings_repo,
                               activity_repo=activity_repo)