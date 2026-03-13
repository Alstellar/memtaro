# db/init_db.py
import asyncpg
from loguru import logger
from .db_settings import SettingsRepo


# Вспомогательная функция для тихой миграции
async def add_column_if_not_exists(conn: asyncpg.Connection, table_name: str, column_name: str, column_type: str):
    """
    Добавляет столбец в таблицу, если его еще нет.
    """
    check_sql = """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = $1 \
                  AND column_name = $2; \
                """
    exists = await conn.fetchval(check_sql, table_name, column_name)

    if not exists:
        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};"
        await conn.execute(alter_sql)
        logger.info(f"➕ Добавлен столбец {column_name} в таблицу {table_name}")


async def create_tables(pool: asyncpg.Pool):
    """
    Создает все необходимые таблицы в базе данных, если они не существуют.
    """
    logger.info("Запуск инициализации таблиц...")
    async with pool.acquire() as conn:
        # --- Таблица users ---
        await conn.execute('''
           CREATE TABLE IF NOT EXISTS users (
               user_id BIGINT UNIQUE,
               username VARCHAR (50),
               added_date_of_birth DATE,
               choice_categories BIGINT DEFAULT 1,
               karma BIGINT DEFAULT 10,
               can_send_msg BOOLEAN DEFAULT true,
               id_referrer BIGINT DEFAULT 0,
               registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               premium_date TIMESTAMP,
               sub_my_freelancer_notes BOOLEAN DEFAULT false,
               activity_level INTEGER DEFAULT 0,
               rank TEXT DEFAULT 'Новичок',
               last_active_date DATE DEFAULT CURRENT_DATE,
               external_activity_score INTEGER DEFAULT 0
               );
           ''')

        # --- Таблица images ---
        await conn.execute('''
           CREATE TABLE IF NOT EXISTS images (
               image_id BIGSERIAL,
               file_id VARCHAR (150) UNIQUE,
               in_bot_collection BOOLEAN,
               file_path TEXT,
               category_animals BOOLEAN DEFAULT false,
               category_cinema BOOLEAN DEFAULT false,
               user_id BIGINT DEFAULT 0,
               watch_month BIGINT DEFAULT 0,
               watch_all BIGINT DEFAULT 0
               );
           ''')

        # --- Таблица wisdom_images ---
        await conn.execute('''
           CREATE TABLE IF NOT EXISTS wisdom_images (
               image_id BIGSERIAL,
               file_id VARCHAR (150) UNIQUE,
               file_path TEXT UNIQUE
               );
           ''')

        # --- Таблица predicts ---
        await conn.execute('''
           CREATE TABLE IF NOT EXISTS predicts (
               user_id BIGINT UNIQUE,
               last_predict_date DATE DEFAULT NULL,
               current_predict_image_id BIGINT DEFAULT 0,
               last_wisdom_date DATE DEFAULT NULL,
               current_wisdom_image_id BIGINT DEFAULT 0
           );
           ''')

        # --- Таблица statistics ---
        await conn.execute("""
           CREATE TABLE IF NOT EXISTS statistics (
               user_id BIGINT PRIMARY KEY,
               spent_stars INTEGER DEFAULT 0,
               spent_karma INTEGER DEFAULT 0,
               count_received_memepredictions INTEGER DEFAULT 0,
               count_received_wisdoms INTEGER DEFAULT 0,
               snowball_throws INTEGER DEFAULT 0,
               snowball_hits INTEGER DEFAULT 0,
               snowball_dodges INTEGER DEFAULT 0,
               internal_activity_count INTEGER DEFAULT 0,
               external_activity_count INTEGER DEFAULT 0
           );
           """)
        # Сразу добавляем строку для общей статистики (user_id = 1)
        await conn.execute("INSERT INTO statistics (user_id) VALUES (1) ON CONFLICT DO NOTHING;")

        # Добавляем новые поля для снежков, если их нет
        await add_column_if_not_exists(conn, "statistics", "snowball_throws", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "statistics", "snowball_hits", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "statistics", "snowball_dodges", "INTEGER DEFAULT 0")

        # Добавляем новые поля для активности, если их нет
        await add_column_if_not_exists(conn, "users", "activity_level", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "users", "rank", "TEXT DEFAULT 'Новичок'")
        await add_column_if_not_exists(conn, "users", "last_active_date", "DATE DEFAULT CURRENT_DATE")
        await add_column_if_not_exists(conn, "users", "external_activity_score", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "statistics", "internal_activity_count", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "statistics", "external_activity_count", "INTEGER DEFAULT 0")

        # --- Таблица settings ---
        await conn.execute("""
           CREATE TABLE IF NOT EXISTS settings (
               setting_key TEXT PRIMARY KEY,
               setting_value TEXT,
               setting_display_name TEXT
           );
           """)

        # --- Таблица bot_images ---
        await conn.execute("""
           CREATE TABLE IF NOT EXISTS bot_images (
               id BIGSERIAL PRIMARY KEY,
               dict_name TEXT NOT NULL,
               ru TEXT NOT NULL,
               en TEXT NOT NULL,
               image TEXT NOT NULL,
               file_id TEXT, 
               UNIQUE (dict_name, image)
               );
           """)

        # --- Таблица chats --- (НОВЫЙ БЛОК)
        await conn.execute("""
           CREATE TABLE IF NOT EXISTS chats (
               chat_id BIGINT PRIMARY KEY,
               chat_name TEXT NOT NULL,
               chat_username TEXT,
               last_activity TIMESTAMPTZ NOT NULL DEFAULT now()
               );
           """)

        # --- Таблица payments_yookassa ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments_yookassa (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,        -- Сумма в рублях
                payload TEXT NOT NULL,          -- Тип покупки (karma_100, sub_30)
                payment_id TEXT NOT NULL,       -- ID платежа от ЮКассы (2e0b...)
                status TEXT DEFAULT 'pending',  -- pending, succeeded, canceled
                created_at TIMESTAMPTZ DEFAULT now()
                );
           """)

        # --- Таблица group_activity ---
        await conn.execute('''
           CREATE TABLE IF NOT EXISTS group_activity
           (
               id          BIGSERIAL PRIMARY KEY,
               chat_id     BIGINT NOT NULL,
               user_id     BIGINT NOT NULL,
               last_active TIMESTAMPTZ DEFAULT NOW(),
               UNIQUE (chat_id, user_id)
           );
           ''')

    # ... (инициализация настроек) ...
    try:
        settings_repo = SettingsRepo(pool)
        await settings_repo.initialize_default_settings()
        logger.info("Настройки по умолчанию инициализированы.")
    except Exception as e:
        logger.error(f"Ошибка при инициализации настроек: {e}")

    logger.success("Инициализация таблиц завершена.")
