# handlers/user/marketplace.py
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery
from aiogram.enums import ChatType

from app.config import settings
from app.services.safe_sender import safe_send_message
from app.services.payment_service import create_yookassa_payment, check_payment_loop
from db.db_payments import PaymentRepo
from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo
from db.db_settings import SettingsRepo  # 👈 Добавлен импорт

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

# 💰 СТАТИЧЕСКАЯ КАРТА (КАРМА -> КЛЮЧИ НАСТРОЕК)
KARMA_PACKAGES_MAP = {
    100: "pack_100_karma_price",
    500: "pack_500_karma_price",
    1000: "pack_1000_karma_price",
}
# ❌ УДАЛЕНЫ hardcoded PREMIUM_PRICE


@router.message(F.text == "🏪 Маркетплейс")
async def marketplace_menu(message: Message, bot: Bot, user_repo):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="✨ Купить карму")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    await safe_send_message(bot, message.chat.id, "<b>🏪 Маркетплейс</b>\n\nВыберите категорию:", user_repo,
                            reply_markup=kb)


@router.message(F.text == "✨ Купить карму")
async def buy_karma_menu(message: Message, bot: Bot, user_repo,
                         settings_repo: SettingsRepo):

    # 1. Генерируем текст списка цен динамически
    price_lines = []
    buttons = []
    row = []

    for amount, setting_key in KARMA_PACKAGES_MAP.items():
        price_rub = await settings_repo.get_setting_value(setting_key, 0)

        # Добавляем строчку в текст
        price_lines.append(f"• <b>{amount} ✨</b> — {price_rub} ₽")

        # Добавляем кнопку
        row.append(KeyboardButton(text=f"Купить {amount} ✨"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    prices_str = "\n".join(price_lines)

    text = (
        "<b>✨ Пополнение баланса</b>\n\n"
        "Выберите пакет кармы:\n"
        f"{prices_str}\n\n"
        "Цены указаны в рублях (₽)."
    )

    buttons.append([KeyboardButton(text="🏪 Маркетплейс")])

    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

    await safe_send_message(bot, message.chat.id, text, user_repo, reply_markup=kb)


# --- ОБРАБОТКА ПОКУПКИ КАРМЫ (РУБЛИ) ---

@router.message(F.text.startswith("Купить"))
async def process_karma_rub_payment(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        payment_repo: PaymentRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo
):
    user_id = message.from_user.id

    try:
        amount_karma = int(message.text.split()[1])
    except (IndexError, ValueError):
        return

    setting_key = KARMA_PACKAGES_MAP.get(amount_karma)
    if not setting_key:
        return

    price_rub = await settings_repo.get_setting_value(setting_key, 0)
    if not price_rub:
        await safe_send_message(bot, user_id, "Ошибка: Цена не найдена в настройках.", user_repo)
        return

    description = f"Покупка {amount_karma} кармы (User {user_id})"
    pay_url, payment_id = await create_yookassa_payment(price_rub, description, user_id)

    payload = f"karma_{amount_karma}"
    await payment_repo.add_payment(
        user_id=user_id,
        amount=price_rub,
        payload=payload,
        payment_id=payment_id,
        status="pending"
    )

    try:
        await bot.send_message(
            settings.bot.LOG_GROUP_ID,
            f"🧾 <b>Создан инвойс (Karma)</b>\n"
            f"User: {message.from_user.full_name} (ID: <code>{user_id}</code>)\n"
            f"Товар: {amount_karma} ✨\n"
            f"Сумма: {price_rub} ₽"
        )
    except Exception:
        pass

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {price_rub}₽", url=pay_url)]
    ])

    await safe_send_message(
        bot, user_id,
        f"Счет на оплату создан!\n\nТовар: <b>{amount_karma} ✨</b>\nСумма: <b>{price_rub} ₽</b>\n\nПосле оплаты карма начислится автоматически в течение нескольких минут!",
        user_repo,
        reply_markup=kb
    )

    asyncio.create_task(check_payment_loop(
        bot, payment_id, user_id, payload, price_rub,
        payment_repo, user_repo, stats_repo, settings_repo
    ))


# --- ОБРАБОТКА ПОДПИСКИ (РУБЛИ) ---

@router.message(F.text == "💳 Подписка")
async def buy_subscription_menu(message: Message, bot: Bot, user_repo, settings_repo: SettingsRepo):

    # 👇 Фетчим цену и множитель для описания
    price = await settings_repo.get_setting_value("sub_30d_price", 99)
    daily_bonus = await settings_repo.get_setting_value("bonus_premium_daily_karma", 50)
    premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2) # 👈 ФЕТЧИМ МНОЖИТЕЛЬ

    text = (
        "<b>💳 Премиум подписка (30 дней)</b>\n\n"
        "🔥 <b>Что дает:</b>\n"
        f"• +{daily_bonus} кармы ежедневно\n"
        f"• х{premium_mult}✨ награды за всё\n\n" # 👈 ИСПОЛЬЗУЕМ ДИНАМИЧЕСКИЙ МНОЖИТЕЛЬ
        f"<b>Цена: {price} ₽</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оформить за {price} ₽", callback_data="buy_premium_rub")]
    ])
    await safe_send_message(bot, message.chat.id, text, user_repo, reply_markup=kb)


@router.callback_query(F.data == "buy_premium_rub")
async def process_premium_rub_payment(
        callback: CallbackQuery,
        bot: Bot,
        user_repo: UserRepo,
        payment_repo: PaymentRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo
):
    await callback.answer()
    user_id = callback.from_user.id

    price_rub = await settings_repo.get_setting_value("sub_30d_price", 99)

    description = f"Премиум подписка 30 дней (User {user_id})"
    pay_url, payment_id = await create_yookassa_payment(price_rub, description, user_id)

    payload = "sub_30"
    await payment_repo.add_payment(
        user_id=user_id,
        amount=price_rub,
        payload=payload,
        payment_id=payment_id,
        status="pending"
    )

    try:
        await bot.send_message(
            settings.bot.LOG_GROUP_ID,
            f"🧾 <b>Создан инвойс (Sub)</b>\n"
            f"User: {callback.from_user.full_name} (ID: <code>{user_id}</code>)\n"
            f"Товар: Premium 30 days\n"
            f"Сумма: {price_rub} ₽"
        )
    except Exception:
        pass

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {price_rub}₽", url=pay_url)]
    ])

    await safe_send_message(
        bot, user_id,
        f"Счет на оплату создан!\n\nТовар: <b>Премиум 30 дней</b>\nСумма: <b>{price_rub} ₽</b>",
        user_repo,
        reply_markup=kb
    )

    asyncio.create_task(check_payment_loop(
        bot, payment_id, user_id, payload, price_rub,
        payment_repo, user_repo, stats_repo, settings_repo
    ))