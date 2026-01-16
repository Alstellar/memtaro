# handlers/user/karma.py
from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.filters import Command

from db.db_users import UserRepo
from db.db_settings import SettingsRepo
from app.services.safe_sender import safe_send_message
from app.keyboards import kb_profile_menu

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text == "✨ Карма")
@router.message(Command("karma"))
async def karma_info_handler(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        settings_repo: SettingsRepo
):
    user_id = message.from_user.id
    user = await user_repo.get_user(user_id)
    current_karma = user.get("karma", 0) if user else 0

    # 1. ПОЛУЧЕНИЕ ЦЕН И МНОЖИТЕЛЕЙ (СПИСАНИЕ)
    p_meme = await settings_repo.get_setting_value("price_repeat_meme", 5)
    p_wisdom = await settings_repo.get_setting_value("price_repeat_wisdom", 5)
    p_snowball = await settings_repo.get_setting_value("price_snowball_throw", 5)

    # 2. ПОЛУЧЕНИЕ БОНУСОВ (ЗАРАБОТОК)
    b_ref_signup = await settings_repo.get_setting_value("bonus_ref_signup", 5)
    b_daily_pred = await settings_repo.get_setting_value("bonus_daily_prediction", 1)
    b_daily_wisdom = await settings_repo.get_setting_value("bonus_daily_wisdom", 1)  # Bonus for Wisdom
    b_meme_appr = await settings_repo.get_setting_value("bonus_meme_approval", 5)

    # 3. ПОЛУЧЕНИЕ ПРЕМИУМ КОЭФФИЦИЕНТОВ
    b_prem_daily_karma = await settings_repo.get_setting_value("bonus_premium_daily_karma", 50)
    mult_prem = await settings_repo.get_setting_value("mult_premium_karma", 2)
    b_author_view = await settings_repo.get_setting_value("bonus_author_per_view", 1)

    text = (
        f"Ваш ID: <code>{user_id}</code>\n"
        f"Текущий баланс кармы: <b>{current_karma}</b> ✨\n\n"
        "--- 💫 <b>Как заработать карму:</b> ---\n"
        # Реферальные бонусы за регистрацию
        f"• +{b_ref_signup}✨ за приглашение друзей по реферальной ссылке\n"
        # Ежедневные бонусы (предсказание + мудрость)
        f"• +{b_daily_pred}✨ за ежедневное получение мем-предсказания\n"
        f"• +{b_daily_wisdom}✨ за ежедневное получение мудрости дня\n"
        # Реферальные бонусы за активность реферала
        f"• +{b_daily_pred}✨ за ежедневное получение мем-предсказания каждого друга\n"
        f"• +{b_meme_appr}✨ за отправку нового мема, успешно прошедшего модерацию\n\n"

        "--- 💳 <b>Что дает подписка:</b> ---\n"
        # Ежедневный бонус
        f"• +{b_prem_daily_karma}✨ ежедневный бонус\n"
        # Множители
        f"• х{mult_prem}✨ увеличение награды за получение мем-предсказания\n"
        f"• х{mult_prem}✨ увеличение всех реферальных наград\n"
        # Авторский бонус
        f"• +{b_author_view}✨ за КАЖДОЕ получение вашего мема как мем-предсказания другими пользователями\n\n"

        "А если и этого недостаточно - у вас есть возможность купить дополнительную карму ✨\n\n"

        "--- 💸 <b>На что можно потратить карму:</b> ---\n"
        f"• -{p_meme}✨ за получение повторного мем-предсказания в течение дня\n"
        f"• -{p_wisdom}✨ за получение повторной мудрости в течение дня\n"
        f"• -{p_snowball}✨ за игру в Снежки\n\n"

        "Спасибо, что вы с нами!"
    )

    await safe_send_message(
        bot=bot,
        user_id=user_id,
        text=text,
        reply_markup=kb_profile_menu(),
        user_repo=user_repo
    )