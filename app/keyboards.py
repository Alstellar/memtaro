# keyboards.py

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    # [KeyboardButton(text="🗺️ Волшебный квест"), KeyboardButton(text="💫 Мистический совет")],
    base_keyboard = [
        [KeyboardButton(text="➕ Добавить мем ➕")],
        [KeyboardButton(text="🔮 Мем-предсказание"), KeyboardButton(text="🧙‍♂️ Мудрость дня")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🏪 Маркетплейс")],
        [KeyboardButton(text="📌 Наши проекты"), KeyboardButton(text="ℹ️ Инфо")],
    ]
    # Добавляем кнопку для админов
    if is_admin:
        base_keyboard.append([KeyboardButton(text="📊 Общая статистика"), KeyboardButton(text="⚙️ Настройки бота")])


    # Остальные кнопки, общие для всех пользователей
    base_keyboard.extend([
        [KeyboardButton(text="📜 Пользовательское соглашение")]
    ])

    return ReplyKeyboardMarkup(keyboard=base_keyboard, resize_keyboard=True)


def kb_profile_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )


def kb_shab_profile_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Шаблон")],
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )


def kb_settings_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✉️ Отправить сообщение"), KeyboardButton(text="📤 Сделать рассылку")],
            [KeyboardButton(text="🔝 Топ мемов за месяц"), KeyboardButton(text="🔝 Общий топ мемов")],
            [KeyboardButton(text="✨ Начислить карму"), KeyboardButton(text="💳 Продлить подписку")],
            [KeyboardButton(text="🖼 Загрузка картинок"), KeyboardButton(text="✨ Настройка цен")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )


def make_mem_inline_kb(price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Новый мем за {price} ✨", callback_data="new_mem_private")],
        [InlineKeyboardButton(text="🔮 Таро, Сонник, Гороскоп 🔮", url="https://t.me/rus_tarot_bot")]
    ])


def make_wisdom_inline_kb(price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Новая мудрость за {price}✨", callback_data="new_wisdom_private")],
        [InlineKeyboardButton(text="🔮 Таро, Сонник, Гороскоп 🔮", url="https://t.me/rus_tarot_bot")]
    ])


def kb_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )

def get_moderation_keyboard(image_id: int, is_animals: bool = False, is_cinema: bool = False) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для модерации с учетом выбранных категорий.
    """
    # Определяем текст кнопок (ставим галочку, если True)
    text_animals = "✅ Животные" if is_animals else "Животные"
    text_cinema = "✅ Фильмы и сериалы" if is_cinema else "Фильмы и сериалы"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=text_animals, callback_data=f"category_2_{image_id}"),
            InlineKeyboardButton(text=text_cinema, callback_data=f"category_3_{image_id}")
        ],
        [
            InlineKeyboardButton(text="Добавить ✅", callback_data=f"add_{image_id}"),
            InlineKeyboardButton(text="Отклонить ❌", callback_data=f"reject_{image_id}")
        ]
    ])