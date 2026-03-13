import asyncpg
from typing import Optional, Any

ALLOWED_IMAGE_UPDATE_FIELDS = {
    "file_id",
    "in_bot_collection",
    "file_path",
    "category_animals",
    "category_cinema",
    "user_id",
    "watch_month",
    "watch_all",
}

class ImageRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_image(self, file_id: str, in_bot_collection: bool, file_path: str, user_id: int) -> Optional[int]:
        """
        Р”РѕР±Р°РІР»СЏРµС‚ РЅРѕРІРѕРµ РёР·РѕР±СЂР°Р¶РµРЅРёРµ.
        Р’РѕР·РІСЂР°С‰Р°РµС‚ image_id РЅРѕРІРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР»Рё None, РµСЃР»Рё РѕРЅРѕ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚.
        """
        sql = """
              INSERT INTO images (file_id, in_bot_collection, file_path, user_id)
              VALUES ($1, $2, $3, $4) ON CONFLICT (file_id) DO NOTHING
            RETURNING image_id; \
              """
        async with self.pool.acquire() as conn:
            # fetchval РІРµСЂРЅРµС‚ image_id РёР»Рё None, РµСЃР»Рё ON CONFLICT СЃСЂР°Р±РѕС‚Р°Р»
            return await conn.fetchval(sql, file_id, in_bot_collection, file_path, user_id)

    async def get_image(self, image_id: int) -> Optional[asyncpg.Record]:
        """
        РџРѕР»СѓС‡Р°РµС‚ РґР°РЅРЅС‹Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕ image_id.
        """
        sql = "SELECT * FROM images WHERE image_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, image_id)

    async def get_image_by_file_id(self, file_id: str) -> Optional[int]:
        """
        РџРѕР»СѓС‡Р°РµС‚ image_id РїРѕ file_id.
        """
        sql = "SELECT image_id FROM images WHERE file_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, file_id)

    async def get_random_image(self) -> Optional[asyncpg.Record]:
        """
        РџРѕР»СѓС‡РµРЅРёРµ СЃР»СѓС‡Р°Р№РЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР· РєРѕР»Р»РµРєС†РёРё Р±РѕС‚Р°.
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
        РџРѕР»СѓС‡РµРЅРёРµ СЃР»СѓС‡Р°Р№РЅРѕРіРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РїРѕ РєР°С‚РµРіРѕСЂРёРё.
        Р’РќРРњРђРќРР•: category_column РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РµР·РѕРїР°СЃРЅРѕР№ (Р±РµР· SQL-РёРЅСЉРµРєС†РёР№).
        """
        # РџСЂРѕСЃС‚Р°СЏ РїСЂРѕРІРµСЂРєР° Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё, С‡С‚Рѕ СЌС‚Рѕ РѕРґРЅРѕ РёР· РёР·РІРµСЃС‚РЅС‹С… РЅР°Рј РїРѕР»РµР№
        if category_column not in ("category_animals", "category_cinema"):
            raise ValueError(f"РќРµРґРѕРїСѓСЃС‚РёРјРѕРµ РёРјСЏ СЃС‚РѕР»Р±С†Р° РґР»СЏ РєР°С‚РµРіРѕСЂРёРё: {category_column}")

        # РСЃРїРѕР»СЊР·СѓРµРј f-string РўРћР›Р¬РљРћ РґР»СЏ РїСЂРѕРІРµСЂРµРЅРЅРѕРіРѕ РёРјРµРЅРё СЃС‚РѕР»Р±С†Р°
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
        Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃР»РѕРІР°СЂСЊ СЃРѕ СЃС‚Р°С‚РёСЃС‚РёРєРѕР№ РїРѕ РёР·РѕР±СЂР°Р¶РµРЅРёСЏРј (total Рё user).
        """
        sql_total = "SELECT COUNT(*) FROM images WHERE in_bot_collection = true;"
        sql_user = "SELECT COUNT(*) FROM images WHERE in_bot_collection = true AND user_id <> $1;"

        async with self.pool.acquire() as conn:
            total_images = await conn.fetchval(sql_total)
            user_images = await conn.fetchval(sql_user, admin_id)
            return {"total_images": total_images, "user_images": user_images}

    async def get_images_statistics_by_user_id(self, user_id: int) -> int:
        """
        Р’РѕР·РІСЂР°С‰Р°РµС‚ РєРѕР»РёС‡РµСЃС‚РІРѕ РёР·РѕР±СЂР°Р¶РµРЅРёР№ РґР»СЏ РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
        """
        sql = "SELECT COUNT(*) FROM images WHERE in_bot_collection = true AND user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, user_id)

    async def get_user_mem_views(self, user_id: int) -> dict[str, int]:
        """
        Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃСѓРјРјСѓ РїСЂРѕСЃРјРѕС‚СЂРѕРІ РјРµРјРѕРІ (month, all) РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
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
        Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃСѓРјРјР°СЂРЅС‹Рµ РїСЂРѕСЃРјРѕС‚СЂС‹ РјРµРјРѕРІ (month, all) РґР»СЏ РІСЃРµР№ РєРѕР»Р»РµРєС†РёРё.
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
        Updates selected image fields.
        """
        if not parameters:
            return

        invalid_fields = set(parameters) - ALLOWED_IMAGE_UPDATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Unsupported image fields for update: {sorted(invalid_fields)}")

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
        РЈРґР°Р»СЏРµС‚ РёР·РѕР±СЂР°Р¶РµРЅРёРµ РїРѕ image_id.
        """
        sql = "DELETE FROM images WHERE image_id = $1;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, image_id)

    async def check_image_exists_by_path(self, file_path: str) -> bool:
        """РџСЂРѕРІРµСЂСЏРµС‚, РµСЃС‚СЊ Р»Рё СѓР¶Рµ РєР°СЂС‚РёРЅРєР° СЃ С‚Р°РєРёРј РїСѓС‚РµРј."""
        sql = "SELECT 1 FROM images WHERE file_path = $1"
        async with self.pool.acquire() as conn:
            return bool(await conn.fetchval(sql, file_path))

    async def add_local_image(self, file_path: str, user_id: int = 0) -> int:
        """
        Р”РѕР±Р°РІР»СЏРµС‚ Р»РѕРєР°Р»СЊРЅС‹Р№ С„Р°Р№Р» РІ Р±Р°Р·Сѓ.
        file_id РѕСЃС‚Р°РІР»СЏРµРј NULL (РѕРЅ РѕР±РЅРѕРІРёС‚СЃСЏ РїСЂРё РїРµСЂРІРѕР№ РѕС‚РїСЂР°РІРєРµ).
        """
        sql = """
              INSERT INTO images (file_path, in_bot_collection, user_id, file_id)
              VALUES ($1, true, $2, NULL) RETURNING image_id; \
              """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, file_path, user_id)

    async def increment_image_views(self, image_id: int):
        """
        РЈРІРµР»РёС‡РёРІР°РµС‚ СЃС‡РµС‚С‡РёРєРё РїСЂРѕСЃРјРѕС‚СЂРѕРІ (РјРµСЃСЏС† Рё РІСЃС‘ РІСЂРµРјСЏ) РЅР° +1.
        COALESCE Р·Р°С‰РёС‰Р°РµС‚ РѕС‚ СЃР»СѓС‡Р°СЏ, РµСЃР»Рё РІ РїРѕР»Рµ Р±С‹Р» NULL (РїСЂРµРІСЂР°С‰Р°РµС‚ РµРіРѕ РІ 0).
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
        Р’РѕР·РІСЂР°С‰Р°РµС‚ С‚РѕРї РјРµРјРѕРІ РїРѕ РїСЂРѕСЃРјРѕС‚СЂР°Рј Р·Р° РјРµСЃСЏС†.
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
        РЎР±СЂР°СЃС‹РІР°РµС‚ СЃС‡РµС‚С‡РёРє РїСЂРѕСЃРјРѕС‚СЂРѕРІ Р·Р° РјРµСЃСЏС† Сѓ РІСЃРµС… РєР°СЂС‚РёРЅРѕРє.
        """
        sql = "UPDATE images SET watch_month = 0;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    async def get_top_memes_all_time(self, limit: int = 10) -> list[asyncpg.Record]:
        """
        Р’РѕР·РІСЂР°С‰Р°РµС‚ С‚РѕРї РјРµРјРѕРІ РїРѕ РїСЂРѕСЃРјРѕС‚СЂР°Рј Р·Р° РІСЃРµ РІСЂРµРјСЏ.
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
