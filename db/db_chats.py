import asyncpg
from typing import Optional
from datetime import datetime


class ChatRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def register_chat(self, chat_id: int, chat_name: str, chat_username: Optional[str]) -> bool:
        """
        Регистрирует группу. Обновляет, если уже существует.
        Возвращает True, если группа была новой, иначе False.
        """
        async with self.pool.acquire() as conn:
            # Сначала проверяем, есть ли чат
            existing = await conn.fetchval("SELECT 1 FROM chats WHERE chat_id = $1", chat_id)

            if not existing:
                # Новая группа — вставляем
                sql_insert = """
                             INSERT INTO chats (chat_id, chat_name, chat_username, last_activity)
                             VALUES ($1, $2, $3, NOW()) ON CONFLICT (chat_id) DO NOTHING; \
                             """
                await conn.execute(sql_insert, chat_id, chat_name, chat_username)
                return True  # Новая
            else:
                # Существующая группа — обновляем
                sql_update = """
                             UPDATE chats
                             SET chat_name     = $2, \
                                 chat_username = $3, \
                                 last_activity = NOW()
                             WHERE chat_id = $1; \
                             """
                await conn.execute(sql_update, chat_id, chat_name, chat_username)
                return False  # Существующая