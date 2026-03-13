# db/db_payments.py
from typing import Optional

import asyncpg


class PaymentRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_payment(
        self,
        user_id: int,
        amount: int,
        payload: str,
        payment_id: str,
        status: str = "pending",
    ) -> Optional[int]:
        """
        Saves a new YooKassa payment row.
        Returns inserted row id or None when payment_id already exists.
        """
        sql = """
            INSERT INTO payments_yookassa (user_id, amount, payload, payment_id, status)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (payment_id) DO NOTHING
            RETURNING id;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, user_id, amount, payload, payment_id, status)

    async def update_status(self, payment_id: str, status: str) -> None:
        sql = "UPDATE payments_yookassa SET status = $1 WHERE payment_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, status, payment_id)

    async def update_status_if_current(
        self,
        payment_id: str,
        current_status: str,
        new_status: str,
    ) -> bool:
        """
        Compare-and-set status update. Returns True only when row was updated.
        """
        sql = """
            UPDATE payments_yookassa
            SET status = $1
            WHERE payment_id = $2 AND status = $3
            RETURNING id;
        """
        async with self.pool.acquire() as conn:
            updated_id = await conn.fetchval(sql, new_status, payment_id, current_status)
            return updated_id is not None

    async def get_payment_status(self, payment_id: str) -> Optional[str]:
        sql = "SELECT status FROM payments_yookassa WHERE payment_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, payment_id)

    async def get_payment(self, payment_id: str) -> Optional[asyncpg.Record]:
        sql = """
            SELECT id, user_id, amount, payload, payment_id, status, created_at
            FROM payments_yookassa
            WHERE payment_id = $1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, payment_id)

    async def get_recoverable_payments(self, limit: int = 200) -> list[asyncpg.Record]:
        """
        Returns unfinished payments that should be re-watched on startup.
        """
        sql = """
            SELECT id, user_id, amount, payload, payment_id, status, created_at
            FROM payments_yookassa
            WHERE status = ANY($1::text[])
            ORDER BY created_at ASC
            LIMIT $2;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, ["pending", "processing"], limit)
