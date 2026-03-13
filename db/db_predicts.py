from datetime import date
from typing import Any, Optional

import asyncpg

ALLOWED_PREDICT_UPDATE_FIELDS = {
    "last_predict_date",
    "current_predict_image_id",
    "last_wisdom_date",
    "current_wisdom_image_id",
}


class PredictRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_predicts(self, user_id: int):
        sql = """
            INSERT INTO predicts (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id)

    async def get_predicts(self, user_id: int) -> Optional[asyncpg.Record]:
        sql = "SELECT * FROM predicts WHERE user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def get_user_ids_with_predict_date(self, target_date: date) -> set[int]:
        sql = "SELECT user_id FROM predicts WHERE last_predict_date = $1;"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, target_date)
            return {row["user_id"] for row in rows}

    async def get_predict_activity_summary(self) -> dict[str, int]:
        """
        Returns aggregated daily/weekly/monthly activity counters.
        """
        sql = """
            SELECT
                COUNT(*) FILTER (WHERE last_predict_date = CURRENT_DATE) AS count_today,
                COUNT(*) FILTER (WHERE last_predict_date >= CURRENT_DATE - INTERVAL '6 day') AS count_week,
                COUNT(*) FILTER (WHERE last_predict_date >= CURRENT_DATE - INTERVAL '29 day') AS count_month
            FROM predicts;
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql)
            return {
                "count_today": row["count_today"] or 0,
                "count_week": row["count_week"] or 0,
                "count_month": row["count_month"] or 0,
            }

    async def update_predicts_parameters(self, user_id: int, **parameters: Any):
        if not parameters:
            return

        invalid_fields = set(parameters) - ALLOWED_PREDICT_UPDATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Unsupported predicts fields for update: {sorted(invalid_fields)}")

        set_clause = ", ".join(
            [f"{param} = ${i + 1}" for i, param in enumerate(parameters.keys())]
        )
        sql = f"""
            UPDATE predicts
            SET {set_clause}
            WHERE user_id = ${len(parameters) + 1};
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, *parameters.values(), user_id)
