from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.types import Message, CallbackQuery

# Наши репозитории
from db.db_users import UserRepo
from db.db_images import ImageRepo
from db.db_wisdom_images import WisdomImageRepo
from db.db_predicts import PredictRepo
from db.db_settings import SettingsRepo
from db.db_statistics import StatisticsRepo

# Наши сервисы
from app.services.prediction_service import process_meme_prediction, process_wisdom_prediction
from app.services.safe_sender import animate_prediction, animate_wisdom

router = Router()
# Ограничиваем работу этого роутера только личными сообщениями
router.message.filter(F.chat.type == ChatType.PRIVATE)


# ========================== МЕМ-ПРЕДСКАЗАНИЕ ==========================

@router.message(F.text == "🔮 Мем-предсказание")
@router.message(Command("mem"))
async def mem_prediction_handler(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        image_repo: ImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo,
        stats_repo: StatisticsRepo
):
    """
    Обработчик запроса на мем (через кнопку меню или команду /mem).
    """
    # 1. Запускаем анимацию (UI)
    await animate_prediction(message)

    # 2. Передаем управление сервису (Бизнес-логика)
    await process_meme_prediction(
        bot=bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        via_callback=False,  # Это не платный повтор по кнопке
        user_repo=user_repo,
        image_repo=image_repo,
        predict_repo=predict_repo,
        settings_repo=settings_repo,
        stats_repo=stats_repo
    )


@router.callback_query(F.data == "new_mem_private")
async def new_mem_callback_handler(
        callback: CallbackQuery,
        bot: Bot,
        user_repo: UserRepo,
        image_repo: ImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo,
        stats_repo: StatisticsRepo
):
    """
    Обработчик кнопки "Новый мем за X кармы".
    """
    await callback.answer()

    # Анимация в том же чате
    await animate_prediction(callback.message)

    await process_meme_prediction(
        bot=bot,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        via_callback=True,  # Это запрос через кнопку (возможен платёж)
        user_repo=user_repo,
        image_repo=image_repo,
        predict_repo=predict_repo,
        settings_repo=settings_repo,
        stats_repo=stats_repo
    )


# ========================== МУДРОСТЬ ДНЯ ==========================

@router.message(F.text == "🧙‍♂️ Мудрость дня")
@router.message(Command("wisdom"))
async def wisdom_prediction_handler(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        wisdom_repo: WisdomImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo,
        stats_repo: StatisticsRepo
):
    """
    Обработчик запроса на мудрость (через кнопку меню или команду /wisdom).
    """
    await animate_wisdom(message)

    await process_wisdom_prediction(
        bot=bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        via_callback=False,
        user_repo=user_repo,
        wisdom_repo=wisdom_repo,
        predict_repo=predict_repo,
        settings_repo=settings_repo,
        stats_repo=stats_repo
    )


@router.callback_query(F.data == "new_wisdom_private")
async def new_wisdom_callback_handler(
        callback: CallbackQuery,
        bot: Bot,
        user_repo: UserRepo,
        wisdom_repo: WisdomImageRepo,
        predict_repo: PredictRepo,
        settings_repo: SettingsRepo,
        stats_repo: StatisticsRepo
):
    """
    Обработчик кнопки "Новая мудрость за X кармы".
    """
    await callback.answer()
    await animate_wisdom(callback.message)

    await process_wisdom_prediction(
        bot=bot,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        via_callback=True,
        user_repo=user_repo,
        wisdom_repo=wisdom_repo,
        predict_repo=predict_repo,
        settings_repo=settings_repo,
        stats_repo=stats_repo
    )