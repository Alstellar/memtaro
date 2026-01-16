# handlers/admin/moderation.py
from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery

from db.db_images import ImageRepo
from db.db_users import UserRepo
from db.db_settings import SettingsRepo
from app.services.moderation_service import approve_meme, reject_meme, toggle_category
from app.keyboards import get_moderation_keyboard

router = Router()


# Эти хэндлеры работают в любом чате (в группе логов), поэтому тип чата не фильтруем жестко,
# но можно проверить, что это админ, если нужно.

@router.callback_query(F.data.startswith("add_"))
async def approve_meme_handler(
        callback: CallbackQuery,
        bot: Bot,
        user_repo: UserRepo,
        image_repo: ImageRepo,
        settings_repo: SettingsRepo
):
    image_id = int(callback.data.split("_")[1])

    # Логика одобрения
    result_text = await approve_meme(
        bot,
        image_id,
        user_repo,
        image_repo,
        settings_repo
    )

    # Редактируем сообщение админа
    original_caption = callback.message.caption or ""
    new_caption = f"{original_caption}\n\n{result_text}"

    await callback.message.edit_caption(caption=new_caption, reply_markup=None)
    await callback.answer("Мем добавлен!")


@router.callback_query(F.data.startswith("reject_"))
async def reject_meme_handler(
        callback: CallbackQuery,
        image_repo: ImageRepo
):
    image_id = int(callback.data.split("_")[1])

    # Логика отклонения
    result_text = await reject_meme(image_id, image_repo)

    original_caption = callback.message.caption or ""
    new_caption = f"{original_caption}\n\n{result_text}"

    await callback.message.edit_caption(caption=new_caption, reply_markup=None)
    await callback.answer("Мем отклонен.")


@router.callback_query(F.data.startswith("category_"))
async def category_toggle_handler(
        callback: CallbackQuery,
        image_repo: ImageRepo
):
    # data format: category_{cat_id}_{image_id}
    parts = callback.data.split("_")
    cat_id = int(parts[1])
    image_id = int(parts[2])

    # Переключаем категорию
    is_animals, is_cinema = await toggle_category(image_id, cat_id, image_repo)

    # Обновляем клавиатуру
    new_kb = get_moderation_keyboard(image_id, is_animals, is_cinema)

    # Обновляем сообщение (без изменения текста, только кнопки)
    # Используем try-except, чтобы не падало, если ничего не изменилось (Telegram API error)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass

    await callback.answer()