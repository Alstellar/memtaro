import asyncpg


TRANSFER_AMOUNT_TO_TAROT = 1000


class KarmaTransferError(Exception):
    """Базовая ошибка переноса кармы."""


class TarotDbNotConfiguredError(KarmaTransferError):
    """Ошибка, когда не настроено подключение к БД Tarot."""


class SourceUserNotFoundError(KarmaTransferError):
    """Ошибка, когда пользователь не найден в текущей БД."""


class TargetUserNotFoundError(KarmaTransferError):
    """Ошибка, когда пользователь не найден в БД Tarot."""


class InsufficientKarmaError(KarmaTransferError):
    """Ошибка, когда у пользователя недостаточно кармы."""

    def __init__(self, current_balance: int, required_amount: int):
        """Сохраняет текущий и требуемый баланс для вывода пользователю."""
        self.current_balance = current_balance
        self.required_amount = required_amount
        super().__init__(
            f"Недостаточно кармы: текущий баланс={current_balance}, требуется={required_amount}"
        )


async def transfer_karma_to_tarot_by_user_id(
    source_pool: asyncpg.Pool,
    tarot_pool: asyncpg.Pool | None,
    user_id: int,
    amount: int = TRANSFER_AMOUNT_TO_TAROT,
) -> tuple[int, int]:
    """Переносит карму из текущего бота в @rus_tarot_bot по одному `user_id`."""
    if tarot_pool is None:
        raise TarotDbNotConfiguredError("Пул БД Tarot не настроен.")

    async with source_pool.acquire() as source_conn:
        async with source_conn.transaction():
            source_user = await source_conn.fetchrow(
                "SELECT karma FROM users WHERE user_id = $1 FOR UPDATE;",
                user_id,
            )
            if not source_user:
                raise SourceUserNotFoundError(
                    f"Пользователь {user_id} не найден в текущей БД."
                )

            current_karma = int(source_user.get("karma") or 0)
            if current_karma < amount:
                raise InsufficientKarmaError(
                    current_balance=current_karma,
                    required_amount=amount,
                )

            await source_conn.execute(
                "UPDATE users SET karma = karma - $1 WHERE user_id = $2;",
                amount,
                user_id,
            )

            async with tarot_pool.acquire() as tarot_conn:
                async with tarot_conn.transaction():
                    target_user = await tarot_conn.fetchrow(
                        "SELECT karma FROM users WHERE user_id = $1 FOR UPDATE;",
                        user_id,
                    )
                    if not target_user:
                        raise TargetUserNotFoundError(
                            f"Пользователь {user_id} не найден в БД @rus_tarot_bot."
                        )

                    await tarot_conn.execute(
                        "UPDATE users SET karma = karma + $1 WHERE user_id = $2;",
                        amount,
                        user_id,
                    )
                    target_balance_after = await tarot_conn.fetchval(
                        "SELECT karma FROM users WHERE user_id = $1;",
                        user_id,
                    )

            source_balance_after = await source_conn.fetchval(
                "SELECT karma FROM users WHERE user_id = $1;",
                user_id,
            )

            await source_conn.execute(
                "INSERT INTO statistics (user_id) VALUES ($1) ON CONFLICT DO NOTHING;",
                user_id,
            )
            await source_conn.execute(
                "INSERT INTO statistics (user_id) VALUES (1) ON CONFLICT DO NOTHING;"
            )
            await source_conn.execute(
                "UPDATE statistics SET spent_karma = spent_karma + $1 WHERE user_id = $2;",
                amount,
                user_id,
            )
            await source_conn.execute(
                "UPDATE statistics SET spent_karma = spent_karma + $1 WHERE user_id = 1;",
                amount,
            )

            return int(source_balance_after or 0), int(target_balance_after or 0)
