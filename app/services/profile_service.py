import asyncpg
from loguru import logger
from datetime import datetime

# Импортируем наши репозитории
from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo


class ProfileService:
    def __init__(self, user_repo: UserRepo, stats_repo: StatisticsRepo):
        self.user_repo = user_repo
        self.stats_repo = stats_repo

    async def get_user_profile_data(self, user_id: int) -> dict:
        """
        Получает полные данные профиля пользователя.
        """
        user_profile = await self.user_repo.get_user_profile(user_id)
        user_activities = await self.stats_repo.get_user_activities(user_id)

        if not user_profile:
            return {}

        profile_data = dict(user_profile)
        
        if user_activities:
            profile_data.update(dict(user_activities))
        
        return profile_data

    async def update_user_activity(self, user_id: int, activity_increment: int = 1):
        """
        Обновляет уровень активности пользователя.
        """
        await self.user_repo.update_user_activity(user_id, activity_increment)

    async def update_user_rank(self, user_id: int, new_rank: str):
        """
        Обновляет звание пользователя.
        """
        await self.user_repo.update_user_rank(user_id, new_rank)

    async def update_external_activity_score(self, user_id: int, score_increment: int):
        """
        Обновляет оценку внешней активности пользователя.
        """
        await self.user_repo.update_external_activity_score(user_id, score_increment)

    async def increment_internal_activity(self, user_id: int, increment: int = 1):
        """
        Увеличивает счетчик внутренней активности пользователя.
        """
        await self.stats_repo.increment_internal_activity(user_id, increment)

    async def increment_external_activity(self, user_id: int, increment: int = 1):
        """
        Увеличивает счетчик внешней активности пользователя.
        """
        await self.stats_repo.increment_external_activity(user_id, increment)

    async def calculate_and_update_user_rank(self, user_id: int):
        """
        Рассчитывает и обновляет звание пользователя на основе его активности и кармы.
        """
        profile_data = await self.get_user_profile_data(user_id)
        
        if not profile_data:
            return

        activity_level = profile_data.get('activity_level', 0)
        external_activity_score = profile_data.get('external_activity_score', 0)
        karma = profile_data.get('karma', 0)
        
        # Расчет общей активности
        total_activity = activity_level + external_activity_score
        
        # Определяем звание на основе общей активности и кармы
        if total_activity >= 1000 or karma >= 10000:
            new_rank = "Легенда"
        elif total_activity >= 500 or karma >= 5000:
            new_rank = "Эксперт"
        elif total_activity >= 200 or karma >= 2000:
            new_rank = "Профессионал"
        elif total_activity >= 50 or karma >= 500:
            new_rank = "Знаток"
        elif total_activity >= 10 or karma >= 100:
            new_rank = "Опытный"
        else:
            new_rank = "Новичок"
            
        await self.update_user_rank(user_id, new_rank)