# app/services/moderation_service.py
import os
from loguru import logger
from aiogram import Bot

from db.db_images import ImageRepo
from db.db_users import UserRepo
from db.db_settings import SettingsRepo  # 👈 Добавлен импорт
from app.services.user_service import is_user_premium
from app.services.safe_sender import safe_send_message


async def approve_meme(
        bot: Bot,
        image_id: int,
        user_repo: UserRepo,
        image_repo: ImageRepo,
        settings_repo: SettingsRepo  # 👈 Добавлен аргумент
) -> str:
    """
    Одобряет мем: включает его в коллекцию, начисляет награду автору.
    Использует динамические настройки для бонусов.
    """
    # 1. Включаем мем в коллекцию
    await image_repo.update_images_parameters(image_id=image_id, in_bot_collection=True)

    # 2. Получаем данные о картинке и авторе
    image = await image_repo.get_image(image_id)
    if not image:
        return "Ошибка: Картинка не найдена в БД."

    sender_id = image.get("user_id")
    if sender_id:
        # 3. Начисляем карму автору
        user = await user_repo.get_user(sender_id)
        if user:
            # 👇 ПОЛУЧАЕМ ДИНАМИЧЕСКИЕ НАСТРОЙКИ
            base_bonus = await settings_repo.get_setting_value("bonus_meme_approval", 5)
            premium_mult = await settings_repo.get_setting_value("mult_premium_karma", 2)

            # Расчет бонуса
            is_premium = await is_user_premium(sender_id, user_repo)
            bonus = base_bonus * premium_mult if is_premium else base_bonus

            new_karma = user["karma"] + bonus
            await user_repo.update_user_profile_parameters(sender_id, karma=new_karma)

            # 4. Уведомляем автора (тихо, если заблокировал)
            await safe_send_message(
                bot=bot,
                user_id=sender_id,
                text=f"🎉 Ваш мем одобрен! Вам начислено <b>+{bonus}</b> ✨ кармы.",
                user_repo=user_repo
            )
            logger.info(f"Мем {image_id} одобрен. Автор {sender_id} получил +{bonus}.")

    return "Картинка добавлена ✅"


async def reject_meme(
        image_id: int,
        image_repo: ImageRepo
) -> str:
    """
    Отклоняет мем: удаляет запись из БД и файл с диска. (Логика не требует настроек)
    """
    image = await image_repo.get_image(image_id)
    if not image:
        return "Ошибка: Картинка уже удалена."

    file_path = image.get("file_path")

    # 1. Удаляем из БД
    await image_repo.delete_image_by_id(image_id)

    # 2. Удаляем файл
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Файл {file_path} удален.")
        except Exception as e:
            logger.error(f"Ошибка удаления файла {file_path}: {e}")

    return "Картинка отклонена ❌"


async def toggle_category(
        image_id: int,
        category_id: int,  # 2=Animals, 3=Cinema
        image_repo: ImageRepo
) -> tuple[bool, bool]:  # Возвращает (is_animals, is_cinema)
    """
    Переключает категорию мема. (Логика не требует настроек)
    """
    image = await image_repo.get_image(image_id)
    if not image:
        return False, False

    is_animals = image["category_animals"]
    is_cinema = image["category_cinema"]

    if category_id == 2:
        is_animals = not is_animals
        await image_repo.update_images_parameters(image_id=image_id, category_animals=is_animals)

    elif category_id == 3:
        is_cinema = not is_cinema
        await image_repo.update_images_parameters(image_id=image_id, category_cinema=is_cinema)

    return is_animals, is_cinema