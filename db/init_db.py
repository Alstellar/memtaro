# db/init_db.py
import asyncpg
from loguru import logger

from .db_settings import SettingsRepo


async def add_column_if_not_exists(
    conn: asyncpg.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    """Adds a column if it does not exist."""
    check_sql = """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = $1
          AND column_name = $2;
    """
    exists = await conn.fetchval(check_sql, table_name, column_name)
    if exists:
        return

    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};"
    await conn.execute(alter_sql)
    logger.info(f"Added column {column_name} to table {table_name}")


async def add_unique_constraint_if_not_exists(
    conn: asyncpg.Connection,
    table_name: str,
    constraint_name: str,
    column_name: str,
) -> None:
    """Adds UNIQUE constraint if missing."""
    check_sql = "SELECT 1 FROM pg_constraint WHERE conname = $1;"
    exists = await conn.fetchval(check_sql, constraint_name)
    if exists:
        return

    alter_sql = (
        f"ALTER TABLE {table_name} "
        f"ADD CONSTRAINT {constraint_name} UNIQUE ({column_name});"
    )
    try:
        await conn.execute(alter_sql)
        logger.info(f"Added unique constraint {constraint_name}")
    except Exception as exc:
        # If historical duplicates exist, startup should not hard-fail.
        logger.error(f"Failed to add unique constraint {constraint_name}: {exc}")


async def create_index_if_not_exists(
    conn: asyncpg.Connection,
    index_name: str,
    table_name: str,
    columns_sql: str,
) -> None:
    sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql});"
    await conn.execute(sql)


async def create_tables(pool: asyncpg.Pool) -> None:
    """Creates all required DB tables and performs lightweight migrations."""
    logger.info("Starting DB initialization...")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT UNIQUE,
                username VARCHAR(50),
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
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                image_id BIGSERIAL,
                file_id VARCHAR(150) UNIQUE,
                in_bot_collection BOOLEAN,
                file_path TEXT,
                category_animals BOOLEAN DEFAULT false,
                category_cinema BOOLEAN DEFAULT false,
                user_id BIGINT DEFAULT 0,
                watch_month BIGINT DEFAULT 0,
                watch_all BIGINT DEFAULT 0
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wisdom_images (
                image_id BIGSERIAL,
                file_id VARCHAR(150) UNIQUE,
                file_path TEXT UNIQUE
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predicts (
                user_id BIGINT UNIQUE,
                last_predict_date DATE DEFAULT NULL,
                current_predict_image_id BIGINT DEFAULT 0,
                last_wisdom_date DATE DEFAULT NULL,
                current_wisdom_image_id BIGINT DEFAULT 0
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS statistics (
                user_id BIGINT PRIMARY KEY,
                spent_stars INTEGER DEFAULT 0,
                spent_karma INTEGER DEFAULT 0,
                count_received_memepredictions INTEGER DEFAULT 0,
                count_received_wisdoms INTEGER DEFAULT 0,
                internal_activity_count INTEGER DEFAULT 0,
                external_activity_count INTEGER DEFAULT 0
            );
            """
        )
        await conn.execute("INSERT INTO statistics (user_id) VALUES (1) ON CONFLICT DO NOTHING;")

        await add_column_if_not_exists(conn, "users", "activity_level", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "users", "rank", "TEXT DEFAULT 'Новичок'")
        await add_column_if_not_exists(conn, "users", "last_active_date", "DATE DEFAULT CURRENT_DATE")
        await add_column_if_not_exists(conn, "users", "external_activity_score", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "statistics", "internal_activity_count", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(conn, "statistics", "external_activity_count", "INTEGER DEFAULT 0")

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                setting_display_name TEXT
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_images (
                id BIGSERIAL PRIMARY KEY,
                dict_name TEXT NOT NULL,
                ru TEXT NOT NULL,
                en TEXT NOT NULL,
                image TEXT NOT NULL,
                file_id TEXT,
                UNIQUE (dict_name, image)
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id BIGINT PRIMARY KEY,
                chat_name TEXT NOT NULL,
                chat_username TEXT,
                last_activity TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments_yookassa (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                payload TEXT NOT NULL,
                payment_id TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )

        # Keep the oldest row per payment_id to safely apply UNIQUE constraint.
        await conn.execute(
            """
            DELETE FROM payments_yookassa p1
            USING payments_yookassa p2
            WHERE p1.payment_id = p2.payment_id
              AND p1.id > p2.id;
            """
        )

        await add_unique_constraint_if_not_exists(
            conn,
            table_name="payments_yookassa",
            constraint_name="payments_yookassa_payment_id_key",
            column_name="payment_id",
        )
        await create_index_if_not_exists(
            conn,
            index_name="idx_payments_status_created_at",
            table_name="payments_yookassa",
            columns_sql="status, created_at",
        )
        await create_index_if_not_exists(
            conn,
            index_name="idx_payments_payment_id",
            table_name="payments_yookassa",
            columns_sql="payment_id",
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_activity (
                id BIGSERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                last_active TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (chat_id, user_id)
            );
            """
        )

    try:
        settings_repo = SettingsRepo(pool)
        await settings_repo.initialize_default_settings()
        logger.info("Default settings initialized.")
    except Exception as exc:
        logger.error(f"Settings initialization failed: {exc}")

    logger.success("DB initialization completed.")
