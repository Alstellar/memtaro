# db/db_activity.py
import asyncpg
from datetime import timedelta
from typing import Optional, List

class ActivityRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def update_activity(self, chat_id: int, user_id: int):
        """
        Обновляет last_active для пользователя в чате.
        Вставляет новую запись, если её нет.
        """
        sql = """
            INSERT INTO group_activity (chat_id, user_id, last_active)
            VALUES ($1, $2, NOW())
            ON CONFLICT (chat_id, user_id) DO UPDATE 
            SET last_active = NOW();
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, chat_id, user_id)

    async def get_active_user_count(self, chat_id: int, days: int = 30) -> int:
        """
        Считает количество УНИКАЛЬНЫХ пользователей, активных в чате за последние N дней.
        """
        sql = """
            SELECT COUNT(DISTINCT user_id)
            FROM group_activity
            WHERE chat_id = $1 
              AND last_active > NOW() - INTERVAL '1 day' * $2;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, chat_id, days)

    async def get_random_active_user(self, chat_id: int, sender_id: int, days: int = 30) -> Optional[int]:
        """
        Выбирает случайного активного пользователя из чата, исключая отправителя.
        Возвращает user_id или None.
        """
        sql = """
            SELECT user_id
            FROM group_activity
            WHERE chat_id = $1 
              AND user_id != $2 -- Исключаем отправителя
              AND last_active > NOW() - INTERVAL '1 day' * $3
            ORDER BY RANDOM()
            LIMIT 1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, chat_id, sender_id, days)