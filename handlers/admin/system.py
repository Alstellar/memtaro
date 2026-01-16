# handlers/admin/system.py
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.config import settings
from db.db_images import ImageRepo
from db.db_wisdom_images import WisdomImageRepo
from db.db_bot_images import BotImageRepo
from db.db_users import UserRepo
from db.db_settings import SettingsRepo
from app.services.admin_service import scan_memes_folder, scan_wisdoms_folder, scan_system_images_folder
from app.services.safe_sender import safe_send_message

router = Router()
router.message.filter(F.from_user.id.in_(settings.bot.ADMIN_IDS))


# --- Хэндлеры сканирования ---

@router.message(Command("scan_memes"))
async def cmd_scan_memes(message: Message, image_repo: ImageRepo):
    await message.answer("📂 Начинаю сканирование папки <b>images</b>...")
    stats = await scan_memes_folder(image_repo)
    await message.answer(
        f"✅ <b>Мемы (images):</b>\n➕ Добавлено: {stats['added']}\n⏭ Пропущено: {stats['skipped']}\n❌ Ошибки: {stats['errors']}"
    )


@router.message(Command("scan_wisdoms"))
async def cmd_scan_wisdoms(message: Message, wisdom_repo: WisdomImageRepo):
    await message.answer("📂 Начинаю сканирование папки <b>daily_wisdoms</b>...")
    stats = await scan_wisdoms_folder(wisdom_repo)
    await message.answer(
        f"✅ <b>Мудрости (daily_wisdoms):</b>\n➕ Добавлено: {stats['added']}\n❌ Ошибки: {stats['errors']}"
    )


@router.message(Command("scan_bot_images"))
async def cmd_scan_system_images(message: Message, bot_image_repo: BotImageRepo):
    await message.answer("📂 Начинаю сканирование папки <b>bot_images</b>...")
    stats = await scan_system_images_folder(bot_image_repo)
    await message.answer(
        f"✅ <b>Системные (bot_images):</b>\n➕ Добавлено: {stats['added']}\n❌ Ошибки: {stats['errors']}"
    )


# --- ГЛАВНЫЙ ХЭНДЛЕР АДМИНКИ ---

@router.message(Command("admin"))
@router.message(F.text == "🛠 Админ команды")
async def cmd_admin_root(
        message: Message,
        user_repo: UserRepo,
        settings_repo: SettingsRepo,
        bot: Bot,
        command: CommandObject | None = None
):
    """
    Единая точка входа: обрабатывает и кнопку меню, и команду /admin.
    """
    args_str = command.args if command else None

    # Если аргументов нет (или нажата кнопка) — выводим обновленную справку
    if not args_str:
        admin_id = message.from_user.id

        text = (
            "🛠 <b>Панель администратора</b>\n\n"
            "<b>Команды файловой системы:</b>\n"
            "/scan_bot_images - Сканировать папку 'bot_images'\n"
            "/scan_memes - Сканировать папку 'images'\n"
            "/scan_wisdoms - Сканировать папку 'daily_wisdoms'\n\n"
            "<b>Управление пользователями:</b>\n"
            f"<code>/admin add_karma {admin_id} 100</code> - Начислить карму\n"
            f"<code>/admin add_premium {admin_id} 30</code> (дней)\n\n"
            f"<b>Настройки (Цены):</b>\n"
            f"<code>/admin set_price price_repeat_meme 5</code>\n"
            f"<code>/admin set_price price_repeat_wisdom 5</code>"
        )
        await message.answer(text)
        return

    # Если аргументы есть — парсим их
    args = args_str.split()
    action = args[0].lower()

    # --- 1. Начислить КАРМУ ---
    if action == "add_karma":
        if len(args) != 3:
            await message.answer("❌ Формат: <code>/admin add_karma ID СУММА</code>")
            return
        try:
            target_id = int(args[1])
            amount = int(args[2])

            user = await user_repo.get_user(target_id)
            if not user:
                await message.answer("❌ Пользователь не найден.")
                return

            new_val = user["karma"] + amount
            await user_repo.update_user_profile_parameters(target_id, karma=new_val)

            await message.answer(f"✅ Карма начислена. Стало: {new_val} ✨")
            await safe_send_message(bot, target_id, f"🎁 Вам начислено <b>{amount}</b> ✨ кармы администратором!",
                                    user_repo)
        except ValueError:
            await message.answer("❌ Ошибка чисел.")

    # --- 2. Продлить ПОДПИСКУ ---
    elif action == "add_premium":
        if len(args) != 3:
            await message.answer("❌ Формат: <code>/admin add_premium ID ДНИ</code>")
            return
        try:
            target_id = int(args[1])
            days = int(args[2])

            user = await user_repo.get_user(target_id)
            if not user:
                await message.answer("❌ Пользователь не найден.")
                return

            now = datetime.now()
            current_prem = user.get("premium_date")

            if current_prem and current_prem > now:
                new_date = current_prem + timedelta(days=days)
            else:
                new_date = now + timedelta(days=days)

            await user_repo.update_user_profile_parameters(target_id, premium_date=new_date)

            fmt_date = new_date.strftime("%d.%m.%Y")
            await message.answer(f"✅ Подписка продлена до: <b>{fmt_date}</b>")
            await safe_send_message(bot, target_id, f"🎁 Ваша подписка продлена до <b>{fmt_date}</b>!", user_repo)
        except ValueError:
            await message.answer("❌ Ошибка чисел.")

    # --- 3. Изменить ЦЕНУ ---
    elif action == "set_price":
        if len(args) != 3:
            await message.answer("❌ Формат: <code>/admin set_price КЛЮЧ ЗНАЧЕНИЕ</code>")
            return

        key = args[1]
        value = args[2]

        await settings_repo.update_setting(key, value)
        await message.answer(f"✅ Настройка <b>{key}</b> обновлена: <code>{value}</code>")

    else:
        await message.answer("❓ Неизвестная команда.")