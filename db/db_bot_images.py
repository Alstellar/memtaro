import asyncpg
from typing import Optional, List

class BotImageRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_unique_dict_names(self) -> List[str]:
        """
        Возвращает список уникальных значений dict_name.
        """
        sql = "SELECT DISTINCT dict_name FROM bot_images;"
        async with self.pool.acquire() as conn:
            records = await conn.fetch(sql)
            return [record['dict_name'] for record in records]

    async def get_bot_image_for_layout(self, dict_name: str, en_value: str) -> Optional[asyncpg.Record]:
        """
        Получает запись по dict_name и en (английскому названию).
        """
        sql = "SELECT * FROM bot_images WHERE dict_name = $1 AND en = $2 LIMIT 1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, dict_name, en_value)

    async def get_bot_image_record_without_file_id(self, dict_name: str) -> Optional[asyncpg.Record]:
        """
        Возвращает первую запись для dict_name, у которой file_id пустой.
        """
        sql = """
            SELECT * FROM bot_images 
            WHERE dict_name = $1 AND (file_id IS NULL OR file_id = '')
            LIMIT 1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, dict_name)

    async def update_bot_image_record_file_id_by_id(self, record_id: int, new_file_id: str):
        """
        Обновляет file_id для записи по ее id.
        """
        sql = "UPDATE bot_images SET file_id = $2 WHERE id = $1;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, record_id, new_file_id)

    async def add_local_bot_image(self, dict_name: str, en_name: str, file_path: str):
        """
        Добавляет системную картинку.
        В поле 'ru' временно пишем то же, что и в 'en',
        так как для логики бота нам важен именно 'en' (ключ поиска) и путь.
        """
        sql = """
              INSERT INTO bot_images (dict_name, ru, en, image, file_id)
              VALUES ($1, $2, $3, $4, NULL) ON CONFLICT (dict_name, image) DO NOTHING; \
              """
        async with self.pool.acquire() as conn:
            # $1=dict_name, $2=ru(заглушка), $3=en(ключ), $4=path
            await conn.execute(sql, dict_name, en_name, en_name, file_path)