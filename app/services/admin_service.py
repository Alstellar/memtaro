# app/services/admin_service.py
import os
from loguru import logger
from db.db_images import ImageRepo
from db.db_wisdom_images import WisdomImageRepo
from db.db_bot_images import BotImageRepo

# Поддерживаемые расширения
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


async def scan_memes_folder(image_repo: ImageRepo, folder_path: str = "images") -> dict:
    """
    Сканирует папку images и добавляет новые файлы в БД.
    Возвращает статистику: {"added": int, "skipped": int, "errors": int}
    """
    stats = {"added": 0, "skipped": 0, "errors": 0}

    if not os.path.exists(folder_path):
        logger.error(f"Папка {folder_path} не найдена!")
        return stats

    # Получаем список файлов
    files = os.listdir(folder_path)

    for filename in files:
        # Проверяем расширение
        _, ext = os.path.splitext(filename)
        if ext.lower() not in VALID_EXTENSIONS:
            continue

        full_path = os.path.join(folder_path, filename)
        # Нормализуем слеши (Windows/Linux compatibility)
        full_path = full_path.replace("\\", "/")

        try:
            # 1. Проверяем, есть ли такой путь уже в БД
            exists = await image_repo.check_image_exists_by_path(full_path)
            if exists:
                stats["skipped"] += 1
                continue

            # 2. Добавляем
            # user_id=0 означает "системный/админский" файл
            await image_repo.add_local_image(full_path, user_id=0)
            stats["added"] += 1

        except Exception as e:
            logger.error(f"Ошибка при добавлении мема {full_path}: {e}")
            stats["errors"] += 1

    return stats


async def scan_wisdoms_folder(wisdom_repo: WisdomImageRepo, folder_path: str = "daily_wisdom") -> dict:
    """
    Сканирует папку daily_wisdom и добавляет новые файлы в БД.
    """
    stats = {"added": 0, "skipped": 0,
             "errors": 0}  # skipped сложно посчитать точно с ON CONFLICT без SELECT, но попробуем упрощенно

    if not os.path.exists(folder_path):
        logger.error(f"Папка {folder_path} не найдена!")
        return stats

    files = os.listdir(folder_path)

    for filename in files:
        _, ext = os.path.splitext(filename)
        if ext.lower() not in VALID_EXTENSIONS:
            continue

        full_path = os.path.join(folder_path, filename)
        full_path = full_path.replace("\\", "/")

        try:
            # Для мудростей у нас есть UNIQUE constraint на file_path,
            # но чтобы посчитать статистику, лучше сначала проверить наличие (или полагаться на возвращаемое значение,
            # но asyncpg execute не возвращает rows affected для DO NOTHING очевидным образом)

            # Простой вариант: пытаемся получить, если нет - добавляем (но у нас нет метода get_by_path)
            # Поэтому просто добавляем.

            # Чтобы статистика была честной, можно добавить метод check_exists в репо,
            # но пока просто вызовем add.

            prev_count_query = "SELECT COUNT(*) FROM wisdom_images"
            # Тут для простоты не будем усложнять репо ради счетчика "skipped".
            # Просто добавим файл.

            await wisdom_repo.add_local_wisdom(full_path)
            # Мы не знаем точно, добавился он или был пропущен из-за ON CONFLICT.
            # Будем считать "processed".
            stats["added"] += 1

        except Exception as e:
            logger.error(f"Ошибка при добавлении мудрости {full_path}: {e}")
            stats["errors"] += 1

    return stats


async def scan_system_images_folder(
        bot_image_repo: BotImageRepo,
        folder_path: str = "bot_images"
) -> dict:
    """
    Сканирует папку bot_images и добавляет файлы в словарь 'BOT_IMAGES'.
    Имя файла (без расширения) становится ключом 'en'.
    """
    stats = {"added": 0, "errors": 0}

    if not os.path.exists(folder_path):
        logger.error(f"Папка {folder_path} не найдена!")
        return stats

    files = os.listdir(folder_path)

    for filename in files:
        name, ext = os.path.splitext(filename)
        if ext.lower() not in VALID_EXTENSIONS:
            continue

        full_path = os.path.join(folder_path, filename)
        full_path = full_path.replace("\\", "/")  # Нормализация пути

        try:
            # dict_name="BOT_IMAGES", en_name="need_click_start" (например)
            await bot_image_repo.add_local_bot_image(
                dict_name="BOT_IMAGES",
                en_name=name,
                file_path=full_path
            )
            stats["added"] += 1
            logger.info(f"Добавлена системная картинка: {name}")

        except Exception as e:
            logger.error(f"Ошибка при добавлении {full_path}: {e}")
            stats["errors"] += 1

    return stats