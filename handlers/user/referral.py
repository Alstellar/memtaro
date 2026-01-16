# handlers/user/referral.py
from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ChatType

from app.services.safe_sender import safe_send_message
from app.keyboards import kb_shab_profile_menu, kb_profile_menu

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text == "🤝 Реф. система")
async def ref_system_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    bot_info = await bot.get_me()

    # Формируем ссылку
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    text = (
        "🎉 <b>Реферальная система</b>\n\n"
        "Приглашайте друзей и получайте бонусы в виде кармы!\n\n"
        f"<b>Ваша реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "Приглашённый пользователь, запустив бота по вашей ссылке, автоматически станет вашим рефералом.\n\n"
        "За активность приглашённых друзей вы будете получать дополнительные бонусы в виде кармы каждый день!"
    )

    await safe_send_message(
        bot=bot,
        user_id=user_id,
        text=text,
        reply_markup=kb_shab_profile_menu()  # Кнопки: Шаблон | Профиль | Главное меню
    )


@router.message(F.text == "📋 Шаблон")
async def ref_template_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    # Текст для пересылки друзьям
    template = (
        f"Привет! Я использую бота <a href=\"{ref_link}\">Мем Таро</a> для получения весёлых мем-предсказаний ежедневно.\n\n"
        "Присоединяйся и получай свою порцию удачи каждый день!\n\n"
    )

    await safe_send_message(
        bot=bot,
        user_id=user_id,
        text=template,
        reply_markup=kb_profile_menu()  # Возврат в профиль
    )