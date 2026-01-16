# handlers/group/prediction.py
from aiogram import Bot, Router, F
from aiogram.filters import Command # Оставляем Command, если нужно, но декораторы удалены
from aiogram.enums import ChatType
from aiogram.types import Message, CallbackQuery

from db.db_users import UserRepo
from db.db_images import ImageRepo
from db.db_wisdom_images import WisdomImageRepo
from db.db_predicts import PredictRepo
from db.db_settings import SettingsRepo
from db.db_statistics import StatisticsRepo
from db.db_bot_images import BotImageRepo
from db.db_chats import ChatRepo

from app.services.prediction_service import process_group_meme, process_group_wisdom # 👈 Service calls now direct


router = Router()
# Фильтр: только группы и супергруппы
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
router.callback_query.filter(F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))


# ❌ УДАЛЕНА: group_mem_handler (Оркестратор handlers/group/activity_tracker.py вызывает process_group_meme напрямую)
# ❌ УДАЛЕНА: group_wisdom_handler (Оркестратор handlers/group/activity_tracker.py вызывает process_group_wisdom напрямую)


@router.callback_query(F.data == "new_mem_group")
async def group_new_mem_callback(
    callback: CallbackQuery, bot: Bot,
    user_repo: UserRepo, image_repo: ImageRepo, predict_repo: PredictRepo,
    settings_repo: SettingsRepo, stats_repo: StatisticsRepo,
    bot_image_repo: BotImageRepo, chat_repo: ChatRepo
):
    """
    Хэндлер для кнопки "Новый мем за X кармы" (Callback-only).
    """
    await callback.answer()

    await process_group_meme( # 👈 Вызов сервиса
        bot=bot, chat_id=callback.message.chat.id, user_id=callback.from_user.id,
        reply_to_message_id=callback.message.message_id,
        via_callback=True,
        user_repo=user_repo, image_repo=image_repo, predict_repo=predict_repo,
        settings_repo=settings_repo, stats_repo=stats_repo,
        bot_image_repo=bot_image_repo, chat_repo=chat_repo,
        chat_title=callback.message.chat.title, chat_username=callback.message.chat.username
    )

@router.callback_query(F.data == "new_wisdom_group")
async def group_new_wisdom_callback(
    callback: CallbackQuery, bot: Bot,
    user_repo: UserRepo, wisdom_repo: WisdomImageRepo, predict_repo: PredictRepo,
    settings_repo: SettingsRepo, stats_repo: StatisticsRepo,
    bot_image_repo: BotImageRepo, chat_repo: ChatRepo
):
    """
    Хэндлер для кнопки "Новая мудрость за X кармы" (Callback-only).
    """
    await callback.answer()

    await process_group_wisdom( # 👈 Вызов сервиса
        bot=bot, chat_id=callback.message.chat.id, user_id=callback.from_user.id,
        reply_to_message_id=callback.message.message_id,
        via_callback=True,
        user_repo=user_repo, wisdom_repo=wisdom_repo, predict_repo=predict_repo,
        settings_repo=settings_repo, stats_repo=stats_repo,
        bot_image_repo=bot_image_repo, chat_repo=chat_repo,
        chat_title=callback.message.chat.title, chat_username=callback.message.chat.username
    )