# handlers/user/start.py
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.enums import ChatType, ChatMemberStatus
from loguru import logger

# Конфиг и Репозитории
from app.config import BotSettings
from db.db_users import UserRepo
from db.db_predicts import PredictRepo
from db.db_statistics import StatisticsRepo
from db.db_settings import SettingsRepo  # 👈 Добавлен импорт

# Общие утилиты
from app.services.user_service import ensure_user_records, is_user_premium
from app.keyboards import get_main_menu_keyboard

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

# --- КОНСТАНТЫ МОДУЛЯ ---

WELCOME_TEXT = (
    "Привет! Я бот с мем-предсказаниями на день.\n\n"
    "Вам доступны следующие команды:\n\n"
    "/mem - мем-предсказание\n"
    "/wisdom - мудрость дня\n"
    "/menu - меню бота\n"
    "/info - о боте\n\n"
    "<a href='https://t.me/rus_tarot_bot'>Гороскоп, Таро и Сонник</a>\n"
)


# --- ЛОКАЛЬНАЯ ЛОГИКА (Регистрация) ---

async def _register_new_user(
        bot: Bot,
        bot_settings: BotSettings,
        user_repo: UserRepo,
        settings_repo: SettingsRepo,  # 👈 Добавлен аргумент
        user_id: int,
        username: str | None,
        first_name: str,
        message_text: str
):
    """
    Локальная функция регистрации. Теперь использует динамические настройки
    для расчета реферального бонуса.
    """
    logger.info(f"Новый пользователь: {user_id} @{username}")

    # 1. Парсим реферала
    parts = message_text.split()
    id_referrer = 0
    id_referrer_log = "0"
    if len(parts) > 1:
        param = parts[1]
        if param.startswith("ref_"):
            try:
                id_referrer = int(param[4:])
                id_referrer_log = str(id_referrer)
            except Exception as e:
                logger.error(f"Ошибка парсинга ref_param: {e}")
                id_referrer = 0
        else:
            id_referrer_log = "TG"

    # 2. Лог в админ-группу
    user_bio = "N/A"
    try:
        user_info = await bot.get_chat(user_id)
        user_bio = user_info.bio or "N/A"
    except Exception:
        pass

    log_text = (
        f"👶 Новая регистрация в боте\n\n"
        f"Имя: {first_name}\n"
        f"Username: @{username}\n"
        f"id: <code>{user_id}</code>\n"
        f"id_referrer: <code>{id_referrer_log}</code>\n"
        f"bio: {user_bio}\n"
    )
    try:
        await bot.send_message(chat_id=bot_settings.LOG_GROUP_ID, text=log_text)
    except Exception as e:
        logger.error(f"Не удалось отправить лог о регистрации: {e}")

    # 3. Добавляем юзера в БД
    await user_repo.add_user(user_id, username=username, id_referrer=id_referrer)

    # 4. Проверяем подписку на канал
    try:
        member = await bot.get_chat_member(bot_settings.CHANNEL_ID, user_id)
        is_sub = member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        )
        await user_repo.update_user_profile_parameters(user_id, sub_my_freelancer_notes=is_sub)
    except Exception as e:
        logger.warning(f"Ошибка проверки подписки при старте {user_id}: {e}")

    # 5. Начисляем бонус рефереру (Используем динамические настройки)
    if id_referrer != 0:
        referrer = await user_repo.get_user(id_referrer)
        if referrer:
            # 👇 ПОЛУЧАЕМ НАСТРОЙКИ
            base_bonus = await settings_repo.get_setting_value("bonus_ref_signup", 5)
            premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

            # Расчет бонуса
            is_ref_premium = await is_user_premium(id_referrer, user_repo)
            bonus = base_bonus * premium_mult if is_ref_premium else base_bonus

            new_karma = referrer.get("karma", 0) + bonus
            await user_repo.update_user_profile_parameters(id_referrer, karma=new_karma)
            logger.info(f"Начислено +{bonus} кармы {id_referrer} за реферала {user_id}.")

            try:
                await bot.send_message(
                    chat_id=id_referrer,
                    text=f"По Вашей ссылке зарегистрировался новый пользователь! +{bonus} к карме ✨"
                )
            except Exception:
                pass


# --- ХЭНДЛЕР ---

@router.message(Command("start"))
async def cmd_start(
        message: Message,
        state: FSMContext,
        bot: Bot,
        bot_settings: BotSettings,
        user_repo: UserRepo,
        predict_repo: PredictRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo  # 👈 Добавлен аргумент
):
    await state.clear()
    user_id = message.from_user.id

    # 1. Гарантируем, что записи в stats/predicts есть
    await ensure_user_records(user_id, predict_repo, stats_repo)

    # 2. Проверяем, новый ли юзер
    user = await user_repo.get_user(user_id)
    if user is None:
        # 3. Запускаем локальную логику регистрации
        await _register_new_user(
            bot=bot,
            bot_settings=bot_settings,
            user_repo=user_repo,
            settings_repo=settings_repo,  # 👈 Передан
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            message_text=message.text
        )

    # 4. Клавиатура
    is_admin = user_id in bot_settings.ADMIN_IDS
    keyboard = get_main_menu_keyboard(is_admin)

    # 5. Приветствие
    await message.answer(WELCOME_TEXT, reply_markup=keyboard)