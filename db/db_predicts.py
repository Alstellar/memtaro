import asyncpg
from typing import Optional, Any

class PredictRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_predicts(self, user_id: int):
        """
        Добавляет запись о предсказаниях для нового пользователя.
        """
        sql = """
            INSERT INTO predicts (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id)

    async def get_predicts(self, user_id: int) -> Optional[asyncpg.Record]:
        """
        Получает запись о предсказаниях пользователя.
        """
        sql = "SELECT * FROM predicts WHERE user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def update_predicts_parameters(self, user_id: int, **parameters: Any):
        """
        Обновляет указанные поля в записи о предсказаниях.
        """
        set_clause = ", ".join([f"{param} = ${i + 1}" for i, param in enumerate(parameters.keys())])
        sql = f"""
            UPDATE predicts
            SET {set_clause}
            WHERE user_id = ${len(parameters) + 1};
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, *parameters.values(), user_id)