import asyncpg
from typing import Optional, Any


class ImageRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_image(self, file_id: str, in_bot_collection: bool, file_path: str, user_id: int) -> Optional[int]:
        """
        Добавляет новое изображение.
        Возвращает image_id нового изображения или None, если оно уже существует.
        """
        sql = """
              INSERT INTO images (file_id, in_bot_collection, file_path, user_id)
              VALUES ($1, $2, $3, $4) ON CONFLICT (file_id) DO NOTHING
            RETURNING image_id; \
              """
        async with self.pool.acquire() as conn:
            # fetchval вернет image_id или None, если ON CONFLICT сработал
            return await conn.fetchval(sql, file_id, in_bot_collection, file_path, user_id)

    async def get_image(self, image_id: int) -> Optional[asyncpg.Record]:
        """
        Получает данные изображения по image_id.
        """
        sql = "SELECT * FROM images WHERE image_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, image_id)

    async def get_image_by_file_id(self, file_id: str) -> Optional[int]:
        """
        Получает image_id по file_id.
        """
        sql = "SELECT image_id FROM images WHERE file_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, file_id)

    async def get_random_image(self) -> Optional[asyncpg.Record]:
        """
        Получение случайного изображения из коллекции бота.
        """
        sql = """
              SELECT * \
              FROM images
              WHERE in_bot_collection = true
              ORDER BY RANDOM() LIMIT 1; \
              """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql)

    async def get_random_image_by_category(self, category_column: str) -> Optional[asyncpg.Record]:
        """
        Получение случайного изображения по категории.
        ВНИМАНИЕ: category_column должна быть безопасной (без SQL-инъекций).
        """
        # Простая проверка безопасности, что это одно из известных нам полей
        if category_column not in ("category_animals", "category_cinema"):
            raise ValueError(f"Недопустимое имя столбца для категории: {category_column}")

        # Используем f-string ТОЛЬКО для проверенного имени столбца
        sql = f"""
            SELECT * FROM images 
            WHERE in_bot_collection = true AND {category_column} = true
            ORDER BY RANDOM() 
            LIMIT 1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql)

    async def get_images_statistics(self, admin_id: int) -> dict[str, int]:
        """
        Возвращает словарь со статистикой по изображениям (total и user).
        """
        sql_total = "SELECT COUNT(*) FROM images WHERE in_bot_collection = true;"
        sql_user = "SELECT COUNT(*) FROM images WHERE in_bot_collection = true AND user_id <> $1;"

        async with self.pool.acquire() as conn:
            total_images = await conn.fetchval(sql_total)
            user_images = await conn.fetchval(sql_user, admin_id)
            return {"total_images": total_images, "user_images": user_images}

    async def get_images_statistics_by_user_id(self, user_id: int) -> int:
        """
        Возвращает количество изображений для конкретного пользователя.
        """
        sql = "SELECT COUNT(*) FROM images WHERE in_bot_collection = true AND user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, user_id)

    async def get_user_mem_views(self, user_id: int) -> dict[str, int]:
        """
        Возвращает сумму просмотров мемов (month, all) для пользователя.
        """
        sql = """
              SELECT COALESCE(SUM(watch_month), 0) AS total_watch_month,
                     COALESCE(SUM(watch_all), 0)   AS total_watch_all
              FROM images
              WHERE user_id = $1; \
              """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(sql, user_id)
            return {"watch_month": record["total_watch_month"], "watch_all": record["total_watch_all"]}

    async def get_overall_image_views(self) -> dict[str, int]:
        """
        Возвращает суммарные просмотры мемов (month, all) для всей коллекции.
        """
        sql = """
              SELECT COALESCE(SUM(watch_month), 0) AS total_watch_month,
                     COALESCE(SUM(watch_all), 0)   AS total_watch_all
              FROM images
              WHERE in_bot_collection = true; \
              """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(sql)
            return {"watch_month": record["total_watch_month"], "watch_all": record["total_watch_all"]}

    async def update_images_parameters(self, image_id: int, **parameters: Any):
        """
        Обновляет указанные поля для изображения.
        """
        set_clause = ", ".join([f"{param} = ${i + 1}" for i, param in enumerate(parameters.keys())])
        sql = f"""
            UPDATE images
            SET {set_clause}
            WHERE image_id = ${len(parameters) + 1};
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, *parameters.values(), image_id)

    async def delete_image_by_id(self, image_id: int):
        """
        Удаляет изображение по image_id.
        """
        sql = "DELETE FROM images WHERE image_id = $1;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, image_id)

    async def check_image_exists_by_path(self, file_path: str) -> bool:
        """Проверяет, есть ли уже картинка с таким путем."""
        sql = "SELECT 1 FROM images WHERE file_path = $1"
        async with self.pool.acquire() as conn:
            return bool(await conn.fetchval(sql, file_path))

    async def add_local_image(self, file_path: str, user_id: int = 0) -> int:
        """
        Добавляет локальный файл в базу.
        file_id оставляем NULL (он обновится при первой отправке).
        """
        sql = """
              INSERT INTO images (file_path, in_bot_collection, user_id, file_id)
              VALUES ($1, true, $2, NULL) RETURNING image_id; \
              """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, file_path, user_id)

    async def increment_image_views(self, image_id: int):
        """
        Увеличивает счетчики просмотров (месяц и всё время) на +1.
        COALESCE защищает от случая, если в поле был NULL (превращает его в 0).
        """
        sql = """
              UPDATE images
              SET watch_month = COALESCE(watch_month, 0) + 1,
                  watch_all   = COALESCE(watch_all, 0) + 1
              WHERE image_id = $1;
              """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, image_id)

    async def get_top_memes_month(self, limit: int = 10) -> list[asyncpg.Record]:
        """
        Возвращает топ мемов по просмотрам за месяц.
        """
        sql = """
              SELECT image_id, user_id, watch_month
              FROM images
              WHERE in_bot_collection = true
              ORDER BY watch_month DESC
                  LIMIT $1; \
              """
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, limit)

    async def reset_monthly_views(self):
        """
        Сбрасывает счетчик просмотров за месяц у всех картинок.
        """
        sql = "UPDATE images SET watch_month = 0;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    async def get_top_memes_all_time(self, limit: int = 10) -> list[asyncpg.Record]:
        """
        Возвращает топ мемов по просмотрам за все время.
        """
        sql = """
              SELECT image_id, user_id, watch_all
              FROM images
              WHERE in_bot_collection = true
              ORDER BY watch_all DESC
                  LIMIT $1; \
              """
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, limit)