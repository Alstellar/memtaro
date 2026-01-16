import asyncpg
from typing import Optional, Any, Literal

# Разрешенные поля для сортировки (защита от SQL-инъекций)
SortField = Literal["snowball_hits", "snowball_dodges", "snowball_throws"]

class StatisticsRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_statistics_entry(self, user_id: int):
        """
        Добавляет запись для нового пользователя в таблицу statistics.
        """
        sql = "INSERT INTO statistics (user_id) VALUES ($1) ON CONFLICT DO NOTHING;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id)

    async def get_statistics_entry(self, user_id: int) -> Optional[asyncpg.Record]:
        """
        Получает строку статистики для заданного user_id.
        """
        sql = "SELECT * FROM statistics WHERE user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def increment_statistics(self, user_id: int, **kwargs: Any):
        """
        Увеличивает (инкрементирует) переданные параметры для user_id
        и для общей статистики (user_id = 1).
        """
        if not kwargs:
            return  # Нет параметров для обновления

        set_clause = ", ".join([f"{k} = {k} + ${i + 2}" for i, (k, _) in enumerate(kwargs.items())])
        values = list(kwargs.values())
        sql = f"UPDATE statistics SET {set_clause} WHERE user_id = $1;"

        async with self.pool.acquire() as conn:
            # Обновляем статистику для конкретного пользователя
            await conn.execute(sql, user_id, *values)
            # Обновляем также общую статистику (user_id = 1)
            await conn.execute(sql, 1, *values)

    async def get_top_snowballers(self, sort_by: SortField, limit: int = 25) -> list[asyncpg.Record]:
        """
        Возвращает топ пользователей, объединяя данные с таблицей users.
        """
        # Валидация имени столбца (на всякий случай)
        if sort_by not in ["snowball_hits", "snowball_dodges", "snowball_throws"]:
            raise ValueError("Invalid sort column")

        sql = f"""
            SELECT s.user_id, u.username, s.{sort_by} as score
            FROM statistics s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.{sort_by} > 0
            ORDER BY s.{sort_by} DESC
            LIMIT $1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, limit)

    async def reset_snowball_stats(self):
        sql = "UPDATE statistics SET snowball_throws = 0, snowball_hits = 0, snowball_dodges = 0;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql)