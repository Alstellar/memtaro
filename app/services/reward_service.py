# app/services/reward_service.py
from loguru import logger

from db.db_users import UserRepo
from db.db_settings import SettingsRepo # 👈 Добавлен импорт
from app.services.user_service import is_user_premium  # Импортируем наш премиум-чекер


async def apply_referral_bonus(
        user_id_who_acted: int,
        user_repo: UserRepo,
        settings_repo: SettingsRepo, # 👈 Добавлен аргумент
        base_bonus: int
):
    """
    Начисляет реферальный бонус (если он есть) за действие пользователя.
    Использует динамический множитель Premium.
    """
    try:
        user = await user_repo.get_user(user_id_who_acted)
        if not user:
            return

        ref_id = user.get("id_referrer", 0)
        if not ref_id:
            return  # У пользователя нет реферера

        referrer = await user_repo.get_user(ref_id)
        if not referrer:
            logger.warning(f"Реферер {ref_id} не найден в БД.")
            return

        # 👇 ПОЛУЧАЕМ МНОЖИТЕЛЬ
        premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

        # Расчет бонуса
        is_ref_premium = await is_user_premium(ref_id, user_repo)
        # 👇 ИСПОЛЬЗУЕМ ДИНАМИЧЕСКИЙ МНОЖИТЕЛЬ
        bonus = base_bonus * premium_mult if is_ref_premium else base_bonus

        new_karma = referrer.get("karma", 0) + bonus
        await user_repo.update_user_profile_parameters(ref_id, karma=new_karma)

        logger.info(f"Рефереру {ref_id} начислено +{bonus} кармы за активность {user_id_who_acted}.")

    except Exception as e:
        logger.error(f"Ошибка в apply_referral_bonus для user {user_id_who_acted}: {e}")