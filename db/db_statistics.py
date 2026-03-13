import asyncpg
from typing import Any, Optional

ALLOWED_STAT_INCREMENT_FIELDS = {
    "spent_stars",
    "spent_karma",
    "count_received_memepredictions",
    "count_received_wisdoms",
    "internal_activity_count",
    "external_activity_count",
}


class StatisticsRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_statistics_entry(self, user_id: int):
        sql = "INSERT INTO statistics (user_id) VALUES ($1) ON CONFLICT DO NOTHING;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id)

    async def get_statistics_entry(self, user_id: int) -> Optional[asyncpg.Record]:
        sql = "SELECT * FROM statistics WHERE user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def increment_statistics(self, user_id: int, **kwargs: Any):
        if not kwargs:
            return

        invalid_fields = set(kwargs) - ALLOWED_STAT_INCREMENT_FIELDS
        if invalid_fields:
            raise ValueError(f"Unsupported statistics fields for increment: {sorted(invalid_fields)}")

        set_clause = ", ".join([f"{k} = {k} + ${i + 2}" for i, (k, _) in enumerate(kwargs.items())])
        values = list(kwargs.values())
        sql = f"UPDATE statistics SET {set_clause} WHERE user_id = $1;"

        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id, *values)
            await conn.execute(sql, 1, *values)

    async def increment_internal_activity(self, user_id: int, increment: int = 1):
        sql = "UPDATE statistics SET internal_activity_count = internal_activity_count + $1 WHERE user_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, increment, user_id)

    async def increment_external_activity(self, user_id: int, increment: int = 1):
        sql = "UPDATE statistics SET external_activity_count = external_activity_count + $1 WHERE user_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, increment, user_id)

    async def get_user_activities(self, user_id: int) -> Optional[asyncpg.Record]:
        sql = """
            SELECT internal_activity_count, external_activity_count
            FROM statistics WHERE user_id = $1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)
