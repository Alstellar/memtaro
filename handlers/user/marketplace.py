import asyncio
from uuid import uuid4

import asyncpg
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from app.config import settings
from app.services.karma_transfer_service import (
    InsufficientKarmaError,
    SourceUserNotFoundError,
    TargetUserNotFoundError,
    TarotDbNotConfiguredError,
    TRANSFER_AMOUNT_TO_TAROT,
    transfer_karma_to_tarot_by_user_id,
)
from app.services.payment_service import create_yookassa_payment, spawn_payment_check
from app.services.safe_sender import safe_send_message
from db.db_payments import PaymentRepo
from db.db_settings import SettingsRepo
from db.db_statistics import StatisticsRepo
from db.db_users import UserRepo

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

KARMA_PACKAGES_MAP = {
    100: "pack_100_karma_price",
    500: "pack_500_karma_price",
    1000: "pack_1000_karma_price",
}

TAROT_PRODUCT_BUTTON = "🪬 Карма для @rus_tarot_bot"
TAROT_TRANSFER_REQUEST_CALLBACK = "transfer_tarot_1000"
TAROT_TRANSFER_CONFIRM_CALLBACK = "transfer_tarot_1000_confirm"
TAROT_TRANSFER_CANCEL_CALLBACK = "transfer_tarot_1000_cancel"
TAROT_TRANSFER_PAYMENT_PAYLOAD = f"transfer_tarot_{TRANSFER_AMOUNT_TO_TAROT}"


@router.message(F.text == "🏪 Маркетплейс")
async def marketplace_menu(message: Message, bot: Bot, user_repo: UserRepo):
    """Показывает главное меню маркетплейса."""
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="✨ Купить карму")],
            [KeyboardButton(text=TAROT_PRODUCT_BUTTON)],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
    )
    await safe_send_message(
        bot,
        message.chat.id,
        "<b>🏪 Маркетплейс</b>\n\nВыберите категорию:",
        user_repo,
        reply_markup=kb,
    )


@router.message(F.text == "✨ Купить карму")
async def buy_karma_menu(
    message: Message,
    bot: Bot,
    user_repo: UserRepo,
    settings_repo: SettingsRepo,
):
    """Показывает список рублевых пакетов кармы."""
    price_lines = []
    buttons = []
    row = []

    for amount, setting_key in KARMA_PACKAGES_MAP.items():
        price_rub = await settings_repo.get_setting_value(setting_key, 0)
        price_lines.append(f"• <b>{amount} ✨</b> — {price_rub} ₽")

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


@router.message(F.text == TAROT_PRODUCT_BUTTON)
async def tarot_transfer_product_card(message: Message, bot: Bot, user_repo: UserRepo):
    """Показывает карточку товара для переноса 1000 кармы в @rus_tarot_bot."""
    user = await user_repo.get_user(message.from_user.id)
    current_karma = int(user["karma"]) if user and user["karma"] is not None else 0

    text = (
        "🪬 Карма для @rus_tarot_bot\n\n"
        "Вы можете перенести карму из текущего бота в бота "
        "<b><a href='https://t.me/rus_tarot_bot'>Таро | Гороскоп</a></b>.\n\n"
        "В нем карма используется для получения раскладов Таро.\n\n"
        f"Минимум для перевода: {TRANSFER_AMOUNT_TO_TAROT} ✨.\n"
        f"Ваша Карма: <b>{current_karma} ✨</b>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Перенести {TRANSFER_AMOUNT_TO_TAROT} ✨",
                    callback_data=TAROT_TRANSFER_REQUEST_CALLBACK,
                )
            ]
        ]
    )
    await safe_send_message(bot, message.chat.id, text, user_repo, reply_markup=kb)


@router.callback_query(F.data == TAROT_TRANSFER_REQUEST_CALLBACK)
async def transfer_tarot_karma_request_callback(
    callback: CallbackQuery,
    bot: Bot,
    user_repo: UserRepo,
):
    """Запрашивает подтверждение перед переносом кармы."""
    await callback.answer()
    user_id = callback.from_user.id
    user = await user_repo.get_user(user_id)
    current_karma = int(user["karma"]) if user and user["karma"] is not None else 0

    text = (
        "⚠️ <b>Подтвердите перевод кармы</b>\n\n"
        f"Будет списано: <b>{TRANSFER_AMOUNT_TO_TAROT} ✨</b>\n"
        "Куда: <b>@rus_tarot_bot</b>\n"
        f"Ваш текущий баланс: <b>{current_karma} ✨</b>\n\n"
        "Подтвердить перевод?"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=TAROT_TRANSFER_CONFIRM_CALLBACK),
                InlineKeyboardButton(text="❌ Отмена", callback_data=TAROT_TRANSFER_CANCEL_CALLBACK),
            ]
        ]
    )

    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass

    await safe_send_message(bot, user_id, text, user_repo, reply_markup=kb)


@router.callback_query(F.data == TAROT_TRANSFER_CANCEL_CALLBACK)
async def transfer_tarot_karma_cancel_callback(callback: CallbackQuery):
    """Отменяет перевод кармы после запроса подтверждения."""
    await callback.answer("Перевод отменен.")
    if callback.message:
        try:
            await callback.message.edit_text("Перевод кармы отменен.")
        except Exception:
            pass


@router.callback_query(F.data == TAROT_TRANSFER_CONFIRM_CALLBACK)
async def transfer_tarot_karma_confirm_callback(
    callback: CallbackQuery,
    bot: Bot,
    pool: asyncpg.Pool,
    tarot_pool: asyncpg.Pool | None,
    user_repo: UserRepo,
    payment_repo: PaymentRepo,
):
    """Выполняет перенос фиксированных 1000 кармы между проектами после подтверждения."""
    await callback.answer("Выполняю перевод...")
    user_id = callback.from_user.id
    request_marker = callback.message.message_id if callback.message else uuid4().hex
    transfer_payment_id = f"transfer_tarot_{user_id}_{request_marker}"

    payment_row_id = await payment_repo.add_payment(
        user_id=user_id,
        amount=TRANSFER_AMOUNT_TO_TAROT,
        payload=TAROT_TRANSFER_PAYMENT_PAYLOAD,
        payment_id=transfer_payment_id,
        status="transfer_processing",
    )
    if payment_row_id is None:
        await safe_send_message(
            bot,
            user_id,
            "Этот перевод уже обрабатывается или уже выполнен.",
            user_repo,
        )
        return

    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    try:
        source_after, target_after = await transfer_karma_to_tarot_by_user_id(
            source_pool=pool,
            tarot_pool=tarot_pool,
            user_id=user_id,
            amount=TRANSFER_AMOUNT_TO_TAROT,
        )
        await payment_repo.update_status(transfer_payment_id, "succeeded")
    except TarotDbNotConfiguredError:
        await payment_repo.update_status(transfer_payment_id, "failed")
        await safe_send_message(
            bot,
            user_id,
            "Перенос временно недоступен: не настроено подключение к БД @rus_tarot_bot.",
            user_repo,
        )
        return
    except SourceUserNotFoundError:
        await payment_repo.update_status(transfer_payment_id, "failed")
        await safe_send_message(
            bot,
            user_id,
            "Ваш профиль в текущем боте не найден. Напишите /start и попробуйте снова.",
            user_repo,
        )
        return
    except TargetUserNotFoundError:
        await payment_repo.update_status(transfer_payment_id, "failed")
        await safe_send_message(
            bot,
            user_id,
            (
                "Профиль в @rus_tarot_bot не найден.\n"
                "Сначала запустите @rus_tarot_bot командой /start, затем повторите перенос."
            ),
            user_repo,
        )
        return
    except InsufficientKarmaError as exc:
        await payment_repo.update_status(transfer_payment_id, "failed")
        await safe_send_message(
            bot,
            user_id,
            (
                f"Недостаточно кармы для перевода.\n"
                f"Нужно: <b>{exc.required_amount} ✨</b>\n"
                f"У вас: <b>{exc.current_balance} ✨</b>"
            ),
            user_repo,
        )
        return
    except Exception:
        await payment_repo.update_status(transfer_payment_id, "failed")
        await safe_send_message(
            bot,
            user_id,
            "Не удалось выполнить перенос. Попробуйте чуть позже.",
            user_repo,
        )
        return

    await safe_send_message(
        bot,
        user_id,
        (
            "✅ Перевод выполнен успешно!\n\n"
            f"Списано в текущем боте: <b>{TRANSFER_AMOUNT_TO_TAROT} ✨</b>\n"
            "Начислено в @rus_tarot_bot: "
            f"<b>{TRANSFER_AMOUNT_TO_TAROT} ✨</b>\n\n"
            f"Ваш баланс здесь: <b>{source_after} ✨</b>\n"
            f"Баланс в @rus_tarot_bot: <b>{target_after} ✨</b>"
        ),
        user_repo,
    )

    try:
        await bot.send_message(
            settings.bot.LOG_GROUP_ID,
            (
                "🔁 <b>Перенос кармы в @rus_tarot_bot</b>\n"
                f"User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                f"Сумма: {TRANSFER_AMOUNT_TO_TAROT} ✨\n"
                f"Transaction: <code>{transfer_payment_id}</code>"
            ),
        )
    except Exception:
        pass


@router.message(F.text.startswith("Купить"))
async def process_karma_rub_payment(
    message: Message,
    bot: Bot,
    pool: asyncpg.Pool,
    user_repo: UserRepo,
    payment_repo: PaymentRepo,
    stats_repo: StatisticsRepo,
    settings_repo: SettingsRepo,
    payment_task_registry: set[asyncio.Task] | None = None,
):
    """Создает платеж в рублях на покупку кармы через YooKassa."""
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
        await safe_send_message(bot, user_id, "Ошибка: цена не найдена в настройках.", user_repo)
        return

    description = f"Покупка {amount_karma} кармы (User {user_id})"
    pay_url, payment_id = await create_yookassa_payment(price_rub, description, user_id)

    payload = f"karma_{amount_karma}"
    payment_row_id = await payment_repo.add_payment(
        user_id=user_id,
        amount=price_rub,
        payload=payload,
        payment_id=payment_id,
        status="pending",
    )
    if payment_row_id is None:
        await safe_send_message(
            bot,
            user_id,
            "Платеж уже зарегистрирован. Проверьте статус оплаты чуть позже.",
            user_repo,
        )
        return

    try:
        await bot.send_message(
            settings.bot.LOG_GROUP_ID,
            f"🧾 <b>Создан инвойс (Karma)</b>\n"
            f"User: {message.from_user.full_name} (ID: <code>{user_id}</code>)\n"
            f"Товар: {amount_karma} ✨\n"
            f"Сумма: {price_rub} ₽",
        )
    except Exception:
        pass

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"Оплатить {price_rub}₽", url=pay_url)]]
    )

    await safe_send_message(
        bot,
        user_id,
        (
            "Счет на оплату создан!\n\n"
            f"Товар: <b>{amount_karma} ✨</b>\n"
            f"Сумма: <b>{price_rub} ₽</b>\n\n"
            "После оплаты карма начислится автоматически в течение нескольких минут!"
        ),
        user_repo,
        reply_markup=kb,
    )

    spawn_payment_check(
        bot=bot,
        payment_id=payment_id,
        user_id=user_id,
        payload=payload,
        amount=price_rub,
        payment_repo=payment_repo,
        user_repo=user_repo,
        stats_repo=stats_repo,
        settings_repo=settings_repo,
        pool=pool,
        task_registry=payment_task_registry,
    )


@router.message(F.text == "💳 Подписка")
async def buy_subscription_menu(
    message: Message,
    bot: Bot,
    user_repo: UserRepo,
    settings_repo: SettingsRepo,
):
    """Показывает карточку премиум-подписки."""
    price = await settings_repo.get_setting_value("sub_30d_price", 99)
    daily_bonus = await settings_repo.get_setting_value("bonus_premium_daily_karma", 50)
    premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

    text = (
        "<b>💳 Премиум подписка (30 дней)</b>\n\n"
        "🔥 <b>Что дает:</b>\n"
        f"• +{daily_bonus} кармы ежедневно\n"
        f"• x{premium_mult}✨ награды за всё\n\n"
        f"<b>Цена: {price} ₽</b>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Оформить за {price} ₽", callback_data="buy_premium_rub")]
        ]
    )
    await safe_send_message(bot, message.chat.id, text, user_repo, reply_markup=kb)


@router.callback_query(F.data == "buy_premium_rub")
async def process_premium_rub_payment(
    callback: CallbackQuery,
    bot: Bot,
    pool: asyncpg.Pool,
    user_repo: UserRepo,
    payment_repo: PaymentRepo,
    stats_repo: StatisticsRepo,
    settings_repo: SettingsRepo,
    payment_task_registry: set[asyncio.Task] | None = None,
):
    """Создает платеж в рублях на премиум-подписку через YooKassa."""
    await callback.answer()
    user_id = callback.from_user.id

    price_rub = await settings_repo.get_setting_value("sub_30d_price", 99)
    description = f"Премиум подписка 30 дней (User {user_id})"
    pay_url, payment_id = await create_yookassa_payment(price_rub, description, user_id)

    payload = "sub_30"
    payment_row_id = await payment_repo.add_payment(
        user_id=user_id,
        amount=price_rub,
        payload=payload,
        payment_id=payment_id,
        status="pending",
    )
    if payment_row_id is None:
        await safe_send_message(
            bot,
            user_id,
            "Платеж уже зарегистрирован. Проверьте статус оплаты чуть позже.",
            user_repo,
        )
        return

    try:
        await bot.send_message(
            settings.bot.LOG_GROUP_ID,
            f"🧾 <b>Создан инвойс (Sub)</b>\n"
            f"User: {callback.from_user.full_name} (ID: <code>{user_id}</code>)\n"
            f"Товар: Premium 30 days\n"
            f"Сумма: {price_rub} ₽",
        )
    except Exception:
        pass

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"Оплатить {price_rub}₽", url=pay_url)]]
    )

    await safe_send_message(
        bot,
        user_id,
        (
            "Счет на оплату создан!\n\n"
            "Товар: <b>Премиум 30 дней</b>\n"
            f"Сумма: <b>{price_rub} ₽</b>"
        ),
        user_repo,
        reply_markup=kb,
    )

    spawn_payment_check(
        bot=bot,
        payment_id=payment_id,
        user_id=user_id,
        payload=payload,
        amount=price_rub,
        payment_repo=payment_repo,
        user_repo=user_repo,
        stats_repo=stats_repo,
        settings_repo=settings_repo,
        pool=pool,
        task_registry=payment_task_registry,
    )
