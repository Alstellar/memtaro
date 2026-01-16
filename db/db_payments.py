# db/db_payments.py
import asyncpg
from typing import Optional


class PaymentRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_payment(
            self,
            user_id: int,
            amount: int,
            payload: str,
            payment_id: str,  # ID от ЮКассы
            status: str = "pending"
    ) -> int:
        """
        Сохраняет новый платеж ЮКассы.
        """
        sql = """
              INSERT INTO payments_yookassa (user_id, amount, payload, payment_id, status)
              VALUES ($1, $2, $3, $4, $5) RETURNING id;
              """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, user_id, amount, payload, payment_id, status)

    async def update_status(self, payment_id: str, status: str):
        """
        Обновляет статус платежа по ID ЮКассы.
        """
        sql = "UPDATE payments_yookassa SET status = $1 WHERE payment_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, status, payment_id)

    async def get_payment_status(self, payment_id: str) -> Optional[str]:
        """
        Получает текущий статус платежа из БД.
        """
        sql = "SELECT status FROM payments_yookassa WHERE payment_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, payment_id)