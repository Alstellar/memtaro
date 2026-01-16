import asyncpg
from typing import Optional, Any


class UserRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # --- Функции создания/получения ---

    async def add_user(self, user_id: int, username: Optional[str], id_referrer: int):
        """
        Добавляет нового пользователя в таблицу.
        Использует ON CONFLICT DO NOTHING для игнорирования дубликатов.
        """
        sql = """
              INSERT INTO users (user_id, username, id_referrer)
              VALUES ($1, $2, $3) ON CONFLICT (user_id) DO NOTHING; \
              """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id, username, id_referrer)

    async def get_user(self, user_id: int) -> Optional[asyncpg.Record]:
        """
        Получает данные пользователя по user_id.
        Возвращает Record или None.
        """
        sql = "SELECT * FROM users WHERE user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def get_all_user_ids(self) -> list[int]:
        """
        Возвращает список ID всех пользователей.
        """
        sql = "SELECT user_id FROM users;"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [row['user_id'] for row in rows]

    # --- Функции обновления ---

    async def update_user_profile_parameters(self, user_id: int, **parameters: Any):
        """
        Обновляет указанные поля для пользователя.
        Пример: await repo.update_user_profile_parameters(123, karma=100, premium_date=datetime.now())
        """
        # Генерируем части SQL-запроса для параметров
        set_clause = ", ".join([f"{param} = ${i + 1}" for i, param in enumerate(parameters.keys())])

        # Формируем полный SQL-запрос
        sql = f"""
            UPDATE users
            SET {set_clause}
            WHERE user_id = ${len(parameters) + 1};
        """

        async with self.pool.acquire() as conn:
            # Выполняем запрос с передачей значений параметров
            await conn.execute(sql, *parameters.values(), user_id)