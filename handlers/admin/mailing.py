# handlers/admin/mailing.py
import asyncio
from loguru import logger

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest

from app.config import settings
from app.fsm_states import Form
from db.db_users import UserRepo

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.message.filter(lambda msg: msg.from_user.id in settings.bot.ADMIN_IDS)


# ================= Вспомогательная функция (Локальная) =================

async def _safe_copy_message(
        bot: Bot,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
        user_repo: UserRepo
) -> bool:
    """
    Локальная функция для копирования сообщения.
    Использует copy_message (поддерживает фото, видео, голосовые).
    Обрабатывает FloodWait и блокировки.
    """
    try:
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id
        )
        return True
    except TelegramRetryAfter as e:
        logger.warning(f"Mailing Flood: {e.retry_after}s. Sleeping...")
        await asyncio.sleep(e.retry_after + 1.0)
        # Рекурсия: пробуем снова
        return await _safe_copy_message(bot, chat_id, from_chat_id, message_id, user_repo)
    except TelegramForbiddenError:
        # Пользователь заблокировал бота -> обновляем БД
        if chat_id > 0:
            await user_repo.update_user_profile_parameters(chat_id, can_send_msg=False)
        return False
    except Exception as e:
        logger.error(f"Mailing error for {chat_id}: {e}")
        return False


# ================= Рассылка ОДНОМУ пользователю (Без изменений) =================

@router.message(F.text == "✉️ Отправить сообщение")
@router.message(Command("mailing_to_one"))
async def mailing_to_one_start(message: Message, state: FSMContext):
    await state.set_state(Form.id_to_msg)
    await message.answer(
        "Введите <b>user_id</b> пользователя, которому нужно отправить сообщение:\n\n"
        "<i>Для отмены введите /cancel</i>"
    )


@router.message(Form.id_to_msg)
async def process_id_to_msg(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return

    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ Некорректный user_id. Это должно быть число.")
        return

    await state.update_data(target_user_id=user_id)
    await state.set_state(Form.text_msg_for_one_user)

    await message.answer(
        f"Отправьте сообщение для пользователя <code>{user_id}</code>.\n"
        "(Текст, фото, видео, стикер — я скопирую всё)."
    )


@router.message(Form.text_msg_for_one_user)
async def process_send_one(message: Message, state: FSMContext, bot: Bot, user_repo: UserRepo):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return

    data = await state.get_data()
    target_id = data.get("target_user_id")

    success = await _safe_copy_message(
        bot=bot,
        chat_id=target_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        user_repo=user_repo
    )

    if success:
        await message.answer(f"✅ Сообщение успешно отправлено пользователю <code>{target_id}</code>.")
    else:
        await message.answer(f"⚠️ Не удалось отправить (блок или ошибка).")

    await state.clear()


# ================= Рассылка ВСЕМ пользователям (С подтверждением и отчетом) =================

@router.message(F.text == "📤 Сделать рассылку")
@router.message(Command("mailing_to_all"))
async def mailing_to_all_start(message: Message, state: FSMContext):
    await state.set_state(Form.text_msg_for_all_users)
    await message.answer(
        "📢 <b>Массовая рассылка</b>\n\n"
        "Отправьте сообщение, которое получат <b>ВСЕ</b> пользователи бота.\n"
        "⚠️ <i>Для отмены введите /cancel</i>"
    )


@router.message(Form.text_msg_for_all_users)
async def process_message_and_confirm(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return

    # Сохраняем ID сообщения и чата, которое нужно будет рассылать
    await state.update_data(
        mailing_msg_id=message.message_id,
        mailing_chat_id=message.chat.id
    )

    # 1. Отправляем тестовое сообщение админу
    await message.answer("✅ Сообщение принято. Вот его превью (как оно будет выглядеть в рассылке):")

    test_msg = await bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )

    # 2. Кнопка подтверждения
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 НАЧАТЬ РАССЫЛКУ", callback_data="mail_confirm"),
            InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="mail_cancel")
        ]
    ])

    await message.answer(
        "<b>⚠️ ВНИМАНИЕ!</b> Рассылка начнется по базе всех пользователей.\n"
        "<b>Подтвердите запуск:</b>",
        reply_markup=confirm_kb
    )

    await state.set_state(Form.waiting_for_confirmation)



@router.callback_query(F.data.in_({"mail_confirm", "mail_cancel"}), Form.waiting_for_confirmation)
async def execute_mass_mailing(callback: CallbackQuery, state: FSMContext, bot: Bot, user_repo: UserRepo):
    await callback.answer()

    data = await state.get_data()

    if callback.data == "mail_cancel":
        await state.clear()
        await callback.message.edit_text("❌ Рассылка отменена.")
        return

    # --- НАЧАЛО РАССЫЛКИ (mail_confirm) ---

    # 1. Очищаем FSM, чтобы бот не ждал подтверждения
    await state.clear()

    # 2. Получаем данные для рассылки
    source_msg_id = data.get("mailing_msg_id")
    source_chat_id = data.get("mailing_chat_id")
    admin_id = callback.from_user.id

    count_total = await user_repo.count_users()
    sendable_user_ids = await user_repo.get_sendable_user_ids()
    count_skipped = max(0, count_total - len(sendable_user_ids))
    count_ok = 0
    count_fail = count_skipped

    # 3. Отправляем начальный отчет и сохраняем его ID для редактирования
    report_text = f"🚀 Рассылка началась!\nОбработано: 0/{count_total}"
    report_msg = await callback.message.answer(report_text)

    # 4. Основной цикл рассылки
    processed = count_skipped
    for idx, uid in enumerate(sendable_user_ids, start=1):
        # 4.1. Копирование сообщения
        success = await _safe_copy_message(
            bot=bot,
            chat_id=uid,
            from_chat_id=source_chat_id,
            message_id=source_msg_id,
            user_repo=user_repo
        )

        if success:
            count_ok += 1
        else:
            count_fail += 1

        processed = count_skipped + idx

        # 4.2. Динамический отчет (каждые 50 пользователей)
        if processed % 50 == 0 or processed == count_total:
            report_text_current = (
                f"⏱️ Рассылка в процессе...\n\n"
                f"Обработано: {processed}/{count_total}\n"
                f"✅ Успешно: {count_ok}\n"
                f"🚫 Не доставлено: {count_fail}"
            )
            # Редактируем сообщение с отчетом
            try:
                await bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=report_msg.message_id,
                    text=report_text_current
                )
            except TelegramBadRequest:
                # Игнорируем, если текст не изменился
                pass

        # 4.3. Пауза для снижения нагрузки
        await asyncio.sleep(0.05)

    # 5. Финальный отчет
    final_report = (
        f"🏁 <b>Рассылка завершена!</b>\n\n"
        f"∑ Всего обработано: <code>{count_total}</code>\n"
        f"✅ Успешно доставлено: <code>{count_ok}</code>\n"
        f"🚫 Не доставлено/Блоки: <code>{count_fail}</code>"
    )

    await bot.edit_message_text(
        chat_id=admin_id,
        message_id=report_msg.message_id,
        text=final_report
    )
