# handlers/admin/moderation.py
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from app.config import settings
from app.keyboards import get_moderation_keyboard
from app.services.moderation_service import approve_meme, reject_meme, toggle_category
from db.db_images import ImageRepo
from db.db_settings import SettingsRepo
from db.db_users import UserRepo

router = Router()


async def _ensure_admin(callback: CallbackQuery) -> bool:
    """Allow moderation actions only for configured admins."""
    if callback.from_user.id not in settings.bot.ADMIN_IDS:
        await callback.answer("Нет доступа к модерации.", show_alert=True)
        return False
    return True


@router.callback_query(F.data.startswith("add_"))
async def approve_meme_handler(
    callback: CallbackQuery,
    bot: Bot,
    user_repo: UserRepo,
    image_repo: ImageRepo,
    settings_repo: SettingsRepo,
):
    if not await _ensure_admin(callback):
        return

    image_id = int(callback.data.split("_")[1])
    result_text = await approve_meme(bot, image_id, user_repo, image_repo, settings_repo)

    original_caption = callback.message.caption or ""
    new_caption = f"{original_caption}\n\n{result_text}"
    await callback.message.edit_caption(caption=new_caption, reply_markup=None)
    await callback.answer("Мем добавлен.")


@router.callback_query(F.data.startswith("reject_"))
async def reject_meme_handler(callback: CallbackQuery, image_repo: ImageRepo):
    if not await _ensure_admin(callback):
        return

    image_id = int(callback.data.split("_")[1])
    result_text = await reject_meme(image_id, image_repo)

    original_caption = callback.message.caption or ""
    new_caption = f"{original_caption}\n\n{result_text}"
    await callback.message.edit_caption(caption=new_caption, reply_markup=None)
    await callback.answer("Мем отклонен.")


@router.callback_query(F.data.startswith("category_"))
async def category_toggle_handler(callback: CallbackQuery, image_repo: ImageRepo):
    if not await _ensure_admin(callback):
        return

    parts = callback.data.split("_")
    cat_id = int(parts[1])
    image_id = int(parts[2])
    is_animals, is_cinema = await toggle_category(image_id, cat_id, image_repo)

    new_kb = get_moderation_keyboard(image_id, is_animals, is_cinema)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass
    await callback.answer()
