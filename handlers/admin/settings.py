# handlers/admin/settings.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType

from app.config import settings
from db.db_images import ImageRepo
from db.db_settings import SettingsRepo

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.message.filter(lambda msg: msg.from_user.id in settings.bot.ADMIN_IDS)

# --- КОНСТАНТЫ ДЛЯ НАВИГАЦИИ И ГРУППИРОВКИ ---

BACK_BUTTON_TEXT = "↩️ Назад (Меню цен)"

# 1. СТАТИЧЕСКАЯ КАРТА: Кнопка -> Список ключей в БД
SETTING_GROUPS = {
    "1️⃣ Цены на Услуги (Карма)": ["price_repeat_meme", "price_repeat_wisdom"],
    "2️⃣ Базовые Награды": ["bonus_daily_prediction", "bonus_daily_wisdom", "bonus_meme_approval", "bonus_ref_signup",
                            "bonus_ref_prediction", "bonus_ref_wisdom", "bonus_channel_sub", "bonus_chat_activity"],
    "3️⃣ Премиум Коэфф.": ["mult_premium_karma", "bonus_premium_daily_karma", "bonus_premium_activation",
                           "bonus_author_per_view"],
    "4️⃣ Рейтинги и RNG": ["limit_top_memes"],
    "5️⃣ Маркетплейс (RUB)": ["pack_100_karma_price", "pack_500_karma_price", "pack_1000_karma_price", "sub_30d_price"],
}


# --- ОСНОВНОЕ МЕНЮ НАСТРОЕК (НЕ ИЗМЕНИЛОСЬ) ---

@router.message(F.text == "⚙️ Настройки бота")
async def admin_settings_menu(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✉️ Отправить сообщение"), KeyboardButton(text="📤 Сделать рассылку")],
            [KeyboardButton(text="🔝 Топ мемов за месяц"), KeyboardButton(text="🔝 Общий топ мемов")],
            [KeyboardButton(text="✨ Настройка цен"), KeyboardButton(text="🛠 Админ команды")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    text = ("<b>⚙️ Панель управления</b>\n\nУправление контентом, статистикой и глобальными настройками бота.")
    await message.answer(text, reply_markup=kb)


# --- ТОПЫ МЕМОВ (ОСТАЛИСЬ БЕЗ ИЗМЕНЕНИЙ) ---

async def _render_top_memes(memes: list, title: str) -> str:
    # ... (код функции остался прежним) ...
    if not memes:
        return f"<b>{title}</b>\n\nПока пусто."

    lines = [f"<b>{title}</b>"]
    for idx, record in enumerate(memes, start=1):
        views = record.get('watch_month') if 'watch_month' in record else record.get('watch_all')
        lines.append(
            f"<b>{idx}.</b> ID: <code>{record['image_id']}</code> • "
            f"User: <code>{record['user_id']}</code> • "
            f"Views: <code>{views}</code>"
        )
    return "\n\n".join(lines)



@router.message(F.text == "🔝 Топ мемов за месяц")
async def top_memes_month_handler(message: Message, image_repo: ImageRepo, settings_repo: SettingsRepo):
    limit = await settings_repo.get_setting_value("limit_top_memes", 10)
    memes = await image_repo.get_top_memes_month(limit=limit)
    text = await _render_top_memes(memes, "Рейтинг за месяц (watch_month)")
    await message.answer(text)


@router.message(F.text == "🔝 Общий топ мемов")
async def top_memes_all_handler(message: Message, image_repo: ImageRepo, settings_repo: SettingsRepo): # 👈 Добавлен settings_repo
    limit = await settings_repo.get_setting_value("limit_top_memes", 10)
    memes = await image_repo.get_top_memes_all_time(limit=limit) # 👈 Используем limit
    text = await _render_top_memes(memes, "Общий рейтинг (watch_all)")
    await message.answer(text)


# -----------------------------------------------
# НОВАЯ ЛОГИКА НАСТРОЙКИ ЦЕН (МНОГОУРОВНЕВОЕ МЕНЮ)
# -----------------------------------------------

@router.message(F.text == "✨ Настройка цен")
async def admin_price_menu(message: Message):
    """
    Первый уровень: выводит категории настроек (Цены, Награды, Рейтинги).
    """
    # Создаем кнопки из ключей нашего словаря
    kb_buttons = [
        [KeyboardButton(text=group_name) for group_name in SETTING_GROUPS.keys() if group_name.startswith(digit)]
        for digit in ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    ]
    # Кнопки возврата
    kb_buttons.append([KeyboardButton(text="🏠 Главное меню")])

    kb = ReplyKeyboardMarkup(keyboard=kb_buttons, resize_keyboard=True)

    await message.answer(
        "<b>⚙️ Настройка цен</b>\n\nВыберите категорию для просмотра и редактирования:",
        reply_markup=kb
    )


@router.message(F.text.in_(SETTING_GROUPS.keys()))
async def show_category_settings(message: Message, settings_repo: SettingsRepo):
    """
    Второй уровень: показывает настройки внутри выбранной категории.
    """
    category_name = message.text
    target_keys = SETTING_GROUPS.get(category_name)

    if not target_keys:
        return  # Защита

    # За один запрос получаем все настройки из БД
    all_settings = await settings_repo.get_settings()

    lines = [f"<b>{category_name}</b>\n\n"]

    # Форматируем вывод, используя список ключей для сохранения порядка
    for key in target_keys:
        setting_data = all_settings.get(key)

        if not setting_data:
            lines.append(f"• ⚠️ <code>{key}</code>: НЕ НАЙДЕНО. Запустите /start для инициализации.")
            continue

        name = setting_data.get("display_name") or key
        val = setting_data.get("value")

        # Готовая команда для копирования и редактирования
        lines.append(
            f"• {name}: <b>{val}</b>\n"
            f"<code>/admin set_price {key} {val}</code>"
        )

    # Клавиатура с кнопкой "Назад"
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BACK_BUTTON_TEXT)],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )

    await message.answer("\n\n".join(lines), reply_markup=kb)


@router.message(F.text == BACK_BUTTON_TEXT)
async def back_to_price_menu(message: Message):
    """
    Возврат на уровень выбора категорий.
    """
    # Вызываем функцию, которая показывает меню категорий
    await admin_price_menu(message)


@router.message(F.text == "🛠 Админ команды")
async def admin_help_shortcut(message: Message):
    """
    Перехватываем кнопку "Админ команды" и вызываем главный админ-роутер.
    """
    # Просто отправляем команду, чтобы сработал хэндлер в admin/system.py
    # Используем message.answer для чистой отправки
    await message.answer("/admin")
