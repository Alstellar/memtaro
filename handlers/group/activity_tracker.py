# handlers/group/activity_tracker.py
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.enums import ChatType

# --- Импорт ВСЕХ необходимых Репозиториев для команд ---
from db.db_activity import ActivityRepo
from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo
from db.db_settings import SettingsRepo
from db.db_images import ImageRepo  # Для мемов
from db.db_wisdom_images import WisdomImageRepo  # Для мудрости
from db.db_predicts import PredictRepo  # Для предсказаний
from db.db_bot_images import BotImageRepo  # Для мемов/мудрости
from db.db_chats import ChatRepo  # Для мемов/мудрости

# --- Импорт Сервисных Функций ---
from app.services.prediction_service import process_group_meme, process_group_wisdom

# Список триггеров (команд и текста), которые нужно обрабатывать
# Важно: Все команды должны быть в нижнем регистре
MEM_TRIGGERS = {"/mem"}
WISDOM_TRIGGERS = {"/wisdom"}

router = Router()
# Фильтр: только группы/супергруппы
router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
# Фильтр: ловим весь текст и подписи (включая команды)
router.message.filter(F.text | F.caption)


@router.message()
async def activity_orchestrator(
        message: Message,
        bot: Bot,
        # Репозитории для общей активности
        activity_repo: ActivityRepo,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo,
        # Репозитории для Prediction
        image_repo: ImageRepo,
        wisdom_repo: WisdomImageRepo,
        predict_repo: PredictRepo,
        bot_image_repo: BotImageRepo,
        chat_repo: ChatRepo
):
    """
    ОРКЕСТРАТОР АКТИВНОСТИ И КОМАНД В ГРУППАХ.
    1. Всегда записывает активность.
    2. Вручную вызывает обработчики команд.
    """
    chat_id = message.chat.id
    user_id = message.from_user.id

    # 1. Парсинг команды
    if not message.text:
        command_text = ""
    else:
        # Нормализация: берем только первое слово/команду и убираем @botname
        text = message.text.lower().strip()
        command_text = text.split('@')[0].split()[0]

    # 2. Игнорируем бота и записываем активность (ВСЕГДА ПЕРВЫЙ ШАГ)
    if user_id == bot.id:
        return

    await activity_repo.update_activity(chat_id, user_id)

    # 3. Проверяем и вызываем команду

    # --- МЕМ (/mem) ---
    if command_text in MEM_TRIGGERS:
        await process_group_meme(
            bot=bot, chat_id=chat_id, user_id=user_id,
            reply_to_message_id=message.message_id,
            via_callback=False,  # Это команда, а не колбэк
            user_repo=user_repo, image_repo=image_repo, predict_repo=predict_repo,
            settings_repo=settings_repo, stats_repo=stats_repo,
            bot_image_repo=bot_image_repo, chat_repo=chat_repo,
            chat_title=message.chat.title, chat_username=message.chat.username
        )
        return

    # --- МУДРОСТЬ (/wisdom) ---
    if command_text in WISDOM_TRIGGERS:
        await process_group_wisdom(
            bot=bot, chat_id=chat_id, user_id=user_id,
            reply_to_message_id=message.message_id,
            via_callback=False,  # Это команда, а не колбэк
            user_repo=user_repo, wisdom_repo=wisdom_repo, predict_repo=predict_repo,
            settings_repo=settings_repo, stats_repo=stats_repo,
            bot_image_repo=bot_image_repo, chat_repo=chat_repo,
            chat_title=message.chat.title, chat_username=message.chat.username
        )
        return

    # 4. Если это не команда, просто выходим (активность уже записана)
