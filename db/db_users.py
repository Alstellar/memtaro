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

    async def update_user_activity(self, user_id: int, activity_increment: int = 1):
        """
        Обновляет уровень активности пользователя.
        """
        sql = """
            UPDATE users
            SET activity_level = activity_level + $1, last_active_date = CURRENT_DATE
            WHERE user_id = $2;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, activity_increment, user_id)

    async def update_user_rank(self, user_id: int, new_rank: str):
        """
        Обновляет звание пользователя.
        """
        sql = "UPDATE users SET rank = $1 WHERE user_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, new_rank, user_id)

    async def update_external_activity_score(self, user_id: int, score_increment: int):
        """
        Обновляет оценку внешней активности пользователя.
        """
        sql = "UPDATE users SET external_activity_score = external_activity_score + $1 WHERE user_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, score_increment, user_id)

    async def get_user_profile(self, user_id: int) -> Optional[asyncpg.Record]:
        """
        Получает данные профиля пользователя по user_id.
        Возвращает Record с информацией для отображения в профиле.
        """
        sql = """
            SELECT user_id, username, karma, activity_level, rank,
                   registration_date, external_activity_score, last_active_date
            FROM users WHERE user_id = $1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def get_user_by_username(self, username: str) -> Optional[asyncpg.Record]:
        """
        Получает данные пользователя по username.
        Возвращает Record с информацией о пользователе.
        """
        sql = "SELECT * FROM users WHERE username = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, username)