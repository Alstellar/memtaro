import asyncpg
from typing import Optional

class WisdomImageRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_random_wisdom_image(self) -> Optional[asyncpg.Record]:
        """
        Получает случайное изображение из таблицы wisdom_images.
        """
        sql = """
            SELECT * FROM wisdom_images 
            ORDER BY RANDOM() 
            LIMIT 1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql)

    async def update_wisdom_file_id(self, image_id: int, file_id: str):
        """
        Обновляет file_id для изображения мудрости.
        """
        sql = """
            UPDATE wisdom_images
            SET file_id = $1
            WHERE image_id = $2
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, file_id, image_id)

    async def get_wisdom_image(self, image_id: int) -> Optional[asyncpg.Record]:
        """
        Получает данные изображения мудрости по image_id.
        """
        sql = "SELECT * FROM wisdom_images WHERE image_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, image_id)

    async def add_local_wisdom(self, file_path: str):
        """
        Добавляет локальную мудрость.
        Используем ON CONFLICT (file_path), так как поле UNIQUE.
        """
        sql = """
              INSERT INTO wisdom_images (file_path, file_id)
              VALUES ($1, NULL) ON CONFLICT (file_path) DO NOTHING;
              """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, file_path)