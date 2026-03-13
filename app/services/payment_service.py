# app/services/payment_service.py
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from aiogram import Bot
from loguru import logger
from yookassa import Configuration, Payment

from app.config import settings
from app.services.safe_sender import safe_send_message
from db.db_payments import PaymentRepo
from db.db_settings import SettingsRepo
from db.db_statistics import StatisticsRepo
from db.db_users import UserRepo

# YooKassa config
Configuration.account_id = settings.bot.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.bot.YOOKASSA_SECRET_KEY.get_secret_value()


async def create_yookassa_payment(amount: int, description: str, user_id: int) -> tuple[str, str]:
    """
    Creates a YooKassa payment and returns (confirmation_url, payment_id).
    SDK call is offloaded to a worker thread because it is sync.
    """
    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/memtaro_bot"},
        "capture": True,
        "description": description,
        "metadata": {"user_id": user_id},
    }
    payment = await asyncio.to_thread(Payment.create, payload, idempotence_key)
    return payment.confirmation.confirmation_url, payment.id


def _register_task(task: asyncio.Task, task_registry: Optional[set[asyncio.Task]]) -> None:
    if task_registry is None:
        return
    task_registry.add(task)
    task.add_done_callback(task_registry.discard)


def spawn_payment_check(
    bot: Bot,
    payment_id: str,
    user_id: int,
    payload: str,
    amount: int,
    payment_repo: PaymentRepo,
    user_repo: UserRepo,
    stats_repo: StatisticsRepo,
    settings_repo: SettingsRepo,
    pool: asyncpg.Pool,
    task_registry: Optional[set[asyncio.Task]] = None,
) -> asyncio.Task:
    """
    Starts payment status watcher with robust error logging.
    """
    task = asyncio.create_task(
        check_payment_loop(
            bot=bot,
            payment_id=payment_id,
            user_id=user_id,
            payload=payload,
            amount=amount,
            payment_repo=payment_repo,
            user_repo=user_repo,
            stats_repo=stats_repo,
            settings_repo=settings_repo,
            pool=pool,
        )
    )
    _register_task(task, task_registry)

    def _on_done(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
        except asyncio.CancelledError:
            logger.info(f"Payment watcher canceled: {payment_id}")
        except Exception as exc:  # pragma: no cover - defensive logging hook
            logger.exception(f"Payment watcher crashed for {payment_id}: {exc}")

    task.add_done_callback(_on_done)
    return task


async def restore_pending_payment_watchers(
    bot: Bot,
    payment_repo: PaymentRepo,
    user_repo: UserRepo,
    stats_repo: StatisticsRepo,
    settings_repo: SettingsRepo,
    pool: asyncpg.Pool,
    task_registry: Optional[set[asyncio.Task]] = None,
    limit: int = 200,
) -> int:
    """
    Re-spawns payment watchers for pending/processing rows after restart.
    """
    recoverable = await payment_repo.get_recoverable_payments(limit=limit)
    for row in recoverable:
        spawn_payment_check(
            bot=bot,
            payment_id=row["payment_id"],
            user_id=row["user_id"],
            payload=row["payload"],
            amount=row["amount"],
            payment_repo=payment_repo,
            user_repo=user_repo,
            stats_repo=stats_repo,
            settings_repo=settings_repo,
            pool=pool,
            task_registry=task_registry,
        )
    if recoverable:
        logger.info(f"Recovered {len(recoverable)} unfinished payment watchers.")
    return len(recoverable)


async def check_payment_loop(
    bot: Bot,
    payment_id: str,
    user_id: int,
    payload: str,
    amount: int,
    payment_repo: PaymentRepo,
    user_repo: UserRepo,
    stats_repo: StatisticsRepo,
    settings_repo: SettingsRepo,
    pool: asyncpg.Pool,
    max_checks: int = 60,
) -> None:
    """
    Background checker: polls payment status every 15s for up to 15 minutes.
    Guarantees single fulfillment using status transitions and advisory lock.
    """
    logger.info(f"Start checking payment {payment_id} for user {user_id}")

    for _ in range(max_checks):
        await asyncio.sleep(15)

        try:
            payment = await asyncio.to_thread(Payment.find_one, payment_id)
            provider_status = payment.status

            if provider_status == "succeeded":
                lock_conn = await pool.acquire()
                got_lock = False
                try:
                    got_lock = await lock_conn.fetchval(
                        "SELECT pg_try_advisory_lock(hashtext($1));", payment_id
                    )
                    if not got_lock:
                        continue

                    current_status = await payment_repo.get_payment_status(payment_id)
                    if current_status in {"succeeded", "canceled", "failed"}:
                        return

                    if current_status == "pending":
                        moved = await payment_repo.update_status_if_current(
                            payment_id, "pending", "processing"
                        )
                        if not moved:
                            continue
                    elif current_status != "processing":
                        # Unknown state, do not fulfill.
                        logger.warning(
                            f"Unexpected payment status for {payment_id}: {current_status}"
                        )
                        return

                    fulfilled = await _fulfill_purchase(
                        bot=bot,
                        pool=pool,
                        user_id=user_id,
                        payload=payload,
                        amount=amount,
                        user_repo=user_repo,
                        stats_repo=stats_repo,
                        settings_repo=settings_repo,
                    )

                    if fulfilled:
                        await payment_repo.update_status_if_current(
                            payment_id, "processing", "succeeded"
                        )
                    else:
                        await payment_repo.update_status_if_current(
                            payment_id, "processing", "failed"
                    )
                    return
                finally:
                    if got_lock:
                        await lock_conn.execute(
                            "SELECT pg_advisory_unlock(hashtext($1));", payment_id
                        )
                    await pool.release(lock_conn)

            elif provider_status == "canceled":
                await payment_repo.update_status_if_current(payment_id, "pending", "canceled")
                await payment_repo.update_status_if_current(payment_id, "processing", "canceled")
                return

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Error checking payment {payment_id}: {exc}")

    logger.info(f"Stop checking payment {payment_id} (timeout)")


async def _fulfill_purchase(
    bot: Bot,
    pool: asyncpg.Pool,
    user_id: int,
    payload: str,
    amount: int,
    user_repo: UserRepo,
    stats_repo: StatisticsRepo,  # kept for backward compatibility/injection symmetry
    settings_repo: SettingsRepo,
) -> bool:
    """
    Grants purchased items. Returns True only after successful DB transaction.
    """
    del stats_repo  # not used directly because writes are transactional via raw SQL

    is_karma = payload.startswith("karma_")
    is_sub = payload.startswith("sub_")
    if not (is_karma or is_sub):
        logger.error(f"Unknown payment payload: {payload}")
        return False

    try:
        karma_add = 0
        days = 0
        bonus = 0
        if is_karma:
            karma_add = int(payload.split("_")[1])
        else:
            days = int(payload.split("_")[1])
            bonus = await settings_repo.get_setting_value("bonus_premium_activation", 100)

        new_karma: int
        new_date: Optional[datetime] = None

        async with pool.acquire() as conn:
            async with conn.transaction():
                user = await conn.fetchrow(
                    "SELECT user_id, karma, premium_date FROM users WHERE user_id = $1 FOR UPDATE;",
                    user_id,
                )
                if not user:
                    logger.error(f"User {user_id} not found during payment fulfillment.")
                    return False

                # Ensure stats rows exist before incrementing.
                await conn.execute(
                    "INSERT INTO statistics (user_id) VALUES ($1) ON CONFLICT DO NOTHING;",
                    user_id,
                )
                await conn.execute(
                    "INSERT INTO statistics (user_id) VALUES (1) ON CONFLICT DO NOTHING;"
                )

                await conn.execute(
                    "UPDATE statistics SET spent_stars = spent_stars + $1 WHERE user_id = $2;",
                    amount,
                    user_id,
                )
                await conn.execute(
                    "UPDATE statistics SET spent_stars = spent_stars + $1 WHERE user_id = 1;",
                    amount,
                )

                if is_karma:
                    await conn.execute(
                        "UPDATE users SET karma = karma + $1 WHERE user_id = $2;",
                        karma_add,
                        user_id,
                    )
                    new_karma = await conn.fetchval(
                        "SELECT karma FROM users WHERE user_id = $1;", user_id
                    )
                else:
                    now = datetime.now()
                    current_prem = user.get("premium_date")
                    if current_prem and current_prem > now:
                        new_date = current_prem + timedelta(days=days)
                    else:
                        new_date = now + timedelta(days=days)

                    await conn.execute(
                        """
                        UPDATE users
                        SET premium_date = $1,
                            karma = karma + $2
                        WHERE user_id = $3;
                        """,
                        new_date,
                        bonus,
                        user_id,
                    )
                    new_karma = await conn.fetchval(
                        "SELECT karma FROM users WHERE user_id = $1;", user_id
                    )

        if is_karma:
            await safe_send_message(
                bot,
                user_id,
                (
                    f"✅ Оплата прошла успешно!\n"
                    f"Начислено: <b>{karma_add}</b> ✨\n"
                    f"Баланс: <b>{new_karma}</b> ✨"
                ),
                user_repo,
            )
            try:
                await bot.send_message(
                    settings.bot.LOG_GROUP_ID,
                    (
                        "💰 <b>Успешная оплата (RUB)</b>\n"
                        f"User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                        f"Товар: {karma_add} Кармы\n"
                        f"Сумма: {amount} ₽"
                    ),
                )
            except Exception:
                pass
        else:
            fmt_date = new_date.strftime("%d.%m.%Y") if new_date else "-"
            await safe_send_message(
                bot,
                user_id,
                (
                    f"✅ Подписка активирована до <b>{fmt_date}</b>!\n\n"
                    f"Бонус: +{bonus} ✨"
                ),
                user_repo,
            )
            try:
                await bot.send_message(
                    settings.bot.LOG_GROUP_ID,
                    (
                        "💎 <b>Успешная оплата (RUB)</b>\n"
                        f"User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                        f"Товар: Подписка {days} дн.\n"
                        f"Сумма: {amount} ₽"
                    ),
                )
            except Exception:
                pass

        return True
    except Exception as exc:
        logger.error(f"Fulfillment failed for payment user={user_id}, payload={payload}: {exc}")
        return False
