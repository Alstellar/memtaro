# handlers/user/upload_meme.py
import time
import os
from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ChatType

from app.config import BotSettings
from db.db_images import ImageRepo
from app.services.safe_sender import safe_send_message
from app.keyboards import get_moderation_keyboard
from db.db_settings import SettingsRepo

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text == "➕ Добавить мем ➕")
async def add_meme_info_handler(message: Message, bot: Bot, user_repo, settings_repo: SettingsRepo):

    # Получаем настройки для описания
    base = await settings_repo.get_setting_value("bonus_meme_approval", 5)
    mult = await settings_repo.get_setting_value("mult_premium_karma", 2)
    prem_bonus = base * mult

    text = (
        "Хочешь поделиться своим мемом? 😊\n\n"
        "Просто отправь картинку сюда, и я добавлю её в коллекцию!\n\n"
        "<b>Важно:</b> отправляемая картинка должна соответствовать нормам этики и законодательства, "
        "не содержать оскорбительного или неприемлемого контента.\n\n"
        "Самые активные авторы и авторы самых повторяющихся в предсказаниях мемов будут награждаться подпиской и дополнительной кармой!\n\n"
        f"<tg-spoiler><i>За каждый одобренный мем вы получите <b>+{base}</b> ✨ кармы (или <b>+{prem_bonus} ✨</b> при наличии активной подписки).\n\n"
        "Обладатели <b>активной подписки</b> получают бонусы в виде кармы за <b>КАЖДЫЙ показ</b> своего загруженного мема</i> 👀</tg-spoiler>"
    )
    await safe_send_message(bot, message.chat.id, text, user_repo)


@router.message(F.photo)
async def handle_user_photo(
        message: Message,
        bot: Bot,
        image_repo: ImageRepo,
        bot_settings: BotSettings,
        user_repo
):
    user_id = message.from_user.id
    photo = message.photo[-1]
    file_id = photo.file_id

    # 1. Проверяем дубликаты
    existing_id = await image_repo.get_image_by_file_id(file_id)
    if existing_id:
        await safe_send_message(bot, user_id, "Эта картинка уже есть в базе! Спасибо 😇", user_repo)
        await bot.send_photo(
            chat_id=bot_settings.LOG_GROUP_ID,
            photo=file_id,
            caption=f"♻️ Дубликат от {message.from_user.full_name} (ID: {user_id})"
        )
        return

    # 2. Скачиваем файл
    unix_time = int(time.time())
    folder_name = "images"  # 👈 Папка images
    os.makedirs(folder_name, exist_ok=True)

    file_path = f"{folder_name}/{user_id}_{unix_time}.jpg"

    try:
        file_info = await bot.get_file(file_id)
        await bot.download_file(file_info.file_path, file_path)
    except Exception as e:
        await safe_send_message(bot, user_id, "Ошибка при загрузке. Попробуйте позже.", user_repo)
        return

    # 3. Сохраняем в БД
    image_id = await image_repo.add_image(
        file_id=file_id,
        in_bot_collection=False,
        file_path=file_path,
        user_id=user_id
    )

    if not image_id:
        os.remove(file_path)
        await safe_send_message(bot, user_id, "Эта картинка уже есть в базе!", user_repo)
        return

    # 4. Отправляем пользователю подтверждение
    await safe_send_message(bot, user_id, "Ваша картинка отправлена на модерацию! 🙏", user_repo)

    # 5. Отправляем админу
    caption = (
        f"🆕 <b>Новый мем</b>\n"
        f"От: {message.from_user.full_name} (ID: <code>{user_id}</code>)\n"
        f"Image ID: <code>{image_id}</code>"
    )

    keyboard = get_moderation_keyboard(image_id, is_animals=False, is_cinema=False)

    try:
        await bot.send_photo(
            chat_id=bot_settings.LOG_GROUP_ID,
            photo=file_id,
            caption=caption,
            reply_markup=keyboard
        )
    except Exception as e:
        pass