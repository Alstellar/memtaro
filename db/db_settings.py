# db/db_settings.py

import asyncpg
from typing import Optional, Any, Union


class SettingsRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def initialize_default_settings(self):
        """
        Инициализирует все настройки по умолчанию (цены, бонусы, коэффициенты RNG),
        если они не существуют.
        """
        # (value, display_name)
        defaults = {
            # --- Цены и лимиты ---
            "price_repeat_meme": ("5", "Цена повторного мема"),
            "price_repeat_wisdom": ("5", "Цена новой мудрости"),
            "price_snowball_throw": ("5", "Стоимость броска снежка"),
            "limit_top_memes": ("10", "Лимит мест в месячном топе мемов"),

            # --- Базовые Награды (Заработки) ---
            "bonus_daily_prediction": ("1", "Базовый бонус за ежедневное предсказание"),
            "bonus_daily_wisdom": ("1", "Базовый бонус за Мудрость дня"),
            "bonus_meme_approval": ("5", "Базовый бонус за одобренный мем"),
            "bonus_ref_signup": ("5", "Базовый бонус рефереру за привлечение"),
            "bonus_ref_prediction": ("1", "Базовый реферальный бонус за предсказание"),
            "bonus_ref_wisdom": ("1", "Базовый реферальный бонус за мудрость дня"),
            "bonus_channel_sub": ("1", "Ежедневный бонус за подписку на канал"),
            "bonus_chat_activity": ("5", "Награда за активность в чатах"),

            # --- Премиум-бонусы и коэффициенты ---
            "mult_premium_karma": ("2", "Общий множитель кармы для Premium (xN)"),
            "bonus_premium_daily_karma": ("50", "Ежедневное начисление кармы для Premium"),
            "bonus_premium_activation": ("100", "Бонус кармы при покупке Premium"),
            "bonus_author_per_view": ("1", "Награда автору-премиуму за каждый показ мема"),

            # --- Игровая механика (Снежок) ---
            "prob_crit_hit": ("5", "Вероятность критического попадания (%)"),
            "prob_crit_miss": ("5", "Вероятность критического промаха (%)"),
            "prob_hit_base": ("50", "Базовая вероятность попадания (%)"),
            "bonus_crit_hit": ("50", "Награда за критическое попадание снежком"),
            "snowball_top_max_reward": ("1000", "Максимальная награда в Топе Снежков (1 место)"),
            "snowball_top_min_reward": ("100", "Минимальная награда в Топе Снежков (25 место)"),
            "snowball_top_limit": ("25", "Количество мест, получающих награду в Топе Снежков"),
            "min_active_users_for_random": ("3", "Мин. число активных пользователей для кнопки 'Случайный бросок'"),

            # --- Маркетплейс (YooKassa, рубли) ---
            "pack_100_karma_price": ("10", "Цена пакета (100 кармы) в рублях"),
            "pack_500_karma_price": ("45", "Цена пакета (500 кармы) в рублях"),
            "pack_1000_karma_price": ("85", "Цена пакета (1000 кармы) в рублях"),
            "sub_30d_price": ("99", "Цена Premium подписки (30 дней) в рублях"),
        }

        for key, (value, display_name) in defaults.items():
            current = await self.get_setting(key)
            if current is None:
                await self.update_setting(key, value, display_name)

    async def get_settings(self) -> dict[str, dict[str, str]]:
        sql = "SELECT setting_key, setting_value, setting_display_name FROM settings;"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return {
                row["setting_key"]: {
                    "value": row["setting_value"],
                    "display_name": row["setting_display_name"]  # 👇 Исправлено
                }
                for row in rows
            }

    async def get_setting(self, key: str) -> Optional[dict[str, str]]:
        sql = "SELECT setting_value, setting_display_name FROM settings WHERE setting_key = $1;"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, key)
            if row:
                return {
                    "value": row["setting_value"],
                    "display_name": row["setting_display_name"]  # 👇 Исправлено
                }
            return None

    async def get_setting_value(self, key: str, default: Union[int, float, str]) -> Union[int, float, str]:
        """
        Получает только значение настройки по ключу и пытается привести его к типу default.
        Возвращает default, если ключ не найден или преобразование не удалось.
        """
        setting_data = await self.get_setting(key)

        if setting_data is None:
            return default  # Настройка не найдена, возвращаем значение по умолчанию

        value = setting_data.get("value")

        try:
            # Пробуем привести значение к типу, который имеет default
            if isinstance(default, int):
                return int(value)
            elif isinstance(default, float):
                return float(value)
            else:
                return str(value)
        except (ValueError, TypeError):
            # Если преобразование не удалось (например, "100a" в int), возвращаем default
            return default

    async def update_setting(self, key: str, value: str, display_name: Optional[str] = None):
        """
        Обновляет или вставляет настройку.
        """
        sql = """
              INSERT INTO settings (setting_key, setting_value, setting_display_name)
              VALUES ($1, $2, $3) ON CONFLICT (setting_key)
              DO UPDATE SET setting_value = EXCLUDED.setting_value, setting_display_name = COALESCE (EXCLUDED.setting_display_name, settings.setting_display_name);
              """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, key, value, display_name)
