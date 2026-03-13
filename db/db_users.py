import asyncpg
from typing import Any, Optional

ALLOWED_USER_UPDATE_FIELDS = {
    "username",
    "added_date_of_birth",
    "choice_categories",
    "karma",
    "can_send_msg",
    "id_referrer",
    "premium_date",
    "sub_my_freelancer_notes",
    "activity_level",
    "rank",
    "last_active_date",
    "external_activity_score",
}


class UserRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_user(self, user_id: int, username: Optional[str], id_referrer: int):
        sql = """
            INSERT INTO users (user_id, username, id_referrer)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id, username, id_referrer)

    async def get_user(self, user_id: int) -> Optional[asyncpg.Record]:
        sql = "SELECT * FROM users WHERE user_id = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def get_all_user_ids(self) -> list[int]:
        sql = "SELECT user_id FROM users;"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [row["user_id"] for row in rows]

    async def count_users(self) -> int:
        sql = "SELECT COUNT(*) FROM users;"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql)

    async def get_sendable_user_ids(self) -> list[int]:
        """
        Returns users who did not block the bot (can_send_msg=true).
        """
        sql = """
            SELECT user_id
            FROM users
            WHERE can_send_msg IS DISTINCT FROM false;
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [row["user_id"] for row in rows]

    async def add_karma_to_active_premium_users(self, bonus: int) -> int:
        """
        Atomically adds karma bonus to all users with active premium subscription.
        Returns number of updated users.
        """
        sql = """
            UPDATE users
            SET karma = karma + $1
            WHERE premium_date IS NOT NULL
              AND premium_date >= NOW()
            RETURNING user_id;
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, bonus)
            return len(rows)

    async def get_channel_bonus_candidates(self) -> list[asyncpg.Record]:
        """
        Returns users marked as subscribed to channel bonus program.
        """
        sql = """
            SELECT user_id, karma
            FROM users
            WHERE sub_my_freelancer_notes = true;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql)

    async def update_user_profile_parameters(self, user_id: int, **parameters: Any):
        if not parameters:
            return

        invalid_fields = set(parameters) - ALLOWED_USER_UPDATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Unsupported user fields for update: {sorted(invalid_fields)}")

        set_clause = ", ".join(
            [f"{param} = ${i + 1}" for i, param in enumerate(parameters.keys())]
        )
        sql = f"""
            UPDATE users
            SET {set_clause}
            WHERE user_id = ${len(parameters) + 1};
        """

        async with self.pool.acquire() as conn:
            await conn.execute(sql, *parameters.values(), user_id)

    async def update_user_activity(self, user_id: int, activity_increment: int = 1):
        sql = """
            UPDATE users
            SET activity_level = activity_level + $1, last_active_date = CURRENT_DATE
            WHERE user_id = $2;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, activity_increment, user_id)

    async def update_user_rank(self, user_id: int, new_rank: str):
        sql = "UPDATE users SET rank = $1 WHERE user_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, new_rank, user_id)

    async def update_external_activity_score(self, user_id: int, score_increment: int):
        sql = "UPDATE users SET external_activity_score = external_activity_score + $1 WHERE user_id = $2;"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, score_increment, user_id)

    async def get_user_profile(self, user_id: int) -> Optional[asyncpg.Record]:
        sql = """
            SELECT user_id, username, karma, activity_level, rank,
                   registration_date, external_activity_score, last_active_date
            FROM users WHERE user_id = $1;
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, user_id)

    async def get_user_by_username(self, username: str) -> Optional[asyncpg.Record]:
        sql = "SELECT * FROM users WHERE username = $1;"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, username)
