# app/services/payment_service.py
import uuid
import asyncio
from loguru import logger
from yookassa import Configuration, Payment

from aiogram import Bot
from datetime import datetime, timedelta

from app.config import settings
from app.services.safe_sender import safe_send_message

# Репозитории
from db.db_users import UserRepo
from db.db_payments import PaymentRepo
from db.db_statistics import StatisticsRepo
from db.db_settings import SettingsRepo  # 👈 Добавлен импорт

# Настройка ЮКассы
Configuration.account_id = settings.bot.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.bot.YOOKASSA_SECRET_KEY.get_secret_value()


async def create_yookassa_payment(
        amount: int,
        description: str,
        user_id: int
) -> tuple[str, str]:
    """
    Создает платеж в ЮКассе.
    Возвращает (url_для_оплаты, payment_id).
    """
    idempotence_key = str(uuid.uuid4())
    payment = Payment.create({
        "amount": {
            "value": f"{amount}.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/memtaro_bot"
        },
        "capture": True,
        "description": description,
        "metadata": {"user_id": user_id}
    }, idempotence_key)

    return payment.confirmation.confirmation_url, payment.id


async def check_payment_loop(
        bot: Bot,
        payment_id: str,
        user_id: int,
        payload: str,
        amount: int,
        payment_repo: PaymentRepo,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo  # 👈 Добавлен аргумент
):
    """
    Фоновая задача: проверяет статус платежа каждые 15 секунд в течение 15 минут (60 раз).
    """
    logger.info(f"Start checking payment {payment_id} for user {user_id}")

    for _ in range(60):
        await asyncio.sleep(15)

        try:
            payment = Payment.find_one(payment_id)

            if payment.status == "succeeded":
                current_status = await payment_repo.get_payment_status(payment_id)
                if current_status == "succeeded":
                    return

                await payment_repo.update_status(payment_id, "succeeded")
                # 👇 Передаем settings_repo
                await _fulfill_purchase(bot, user_id, payload, amount, user_repo, stats_repo, settings_repo)
                return

            elif payment.status == "canceled":
                await payment_repo.update_status(payment_id, "canceled")
                return

        except Exception as e:
            logger.error(f"Error checking payment {payment_id}: {e}")

    logger.info(f"Stop checking payment {payment_id} (timeout)")


async def _fulfill_purchase(
        bot: Bot,
        user_id: int,
        payload: str,
        amount: int,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        settings_repo: SettingsRepo  # 👈 Добавлен аргумент
):
    """
    Выдача товара после успешной оплаты.
    """
    user = await user_repo.get_user(user_id)
    if not user: return

    # 1. Обновляем статистику (spent_stars, которое теперь хранит рубли)
    await stats_repo.increment_statistics(user_id, spent_stars=amount)

    # 2. Логика выдачи
    if payload.startswith("karma_"):
        karma_add = int(payload.split("_")[1])
        new_karma = user["karma"] + karma_add

        await user_repo.update_user_profile_parameters(user_id, karma=new_karma)

        await safe_send_message(
            bot, user_id,
            f"✅ Оплата прошла успешно!\nНачислено: <b>{karma_add}</b> ✨\nБаланс: <b>{new_karma}</b> ✨",
            user_repo
        )

        # Лог об успешной оплате
        try:
            await bot.send_message(
                settings.bot.LOG_GROUP_ID,
                f"💰 <b>Успешная оплата (RUB)</b>\n"
                f"User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                f"Товар: {karma_add} Кармы\n"
                f"Сумма: {amount} ₽"
            )
        except Exception:
            pass

    elif payload.startswith("sub_"):
        days = int(payload.split("_")[1])
        now = datetime.now()
        current_prem = user.get("premium_date")

        # 👇 ПОЛУЧАЕМ НАСТРОЙКИ
        bonus = await settings_repo.get_setting_value("bonus_premium_activation", 100)

        # 3. Расчет новой даты (Продление)
        if current_prem and current_prem > now:
            new_date = current_prem + timedelta(days=days)
        else:
            new_date = now + timedelta(days=days)

        # 4. Начисление бонуса
        new_karma = user["karma"] + bonus

        await user_repo.update_user_profile_parameters(user_id, premium_date=new_date, karma=new_karma)

        fmt_date = new_date.strftime("%d.%m.%Y")
        await safe_send_message(
            bot, user_id,
            f"✅ Подписка активирована до <b>{fmt_date}</b>!\n\nБонус: +{bonus} ✨",
            user_repo
        )

        # Лог об успешной оплате
        try:
            await bot.send_message(
                settings.bot.LOG_GROUP_ID,
                f"💎 <b>Успешная оплата (RUB)</b>\n"
                f"User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                f"Товар: Подписка {days} дн.\n"
                f"Сумма: {amount} ₽"
            )
        except Exception:
            pass