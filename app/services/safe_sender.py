# app/services/safe_sender.py
import asyncio
from loguru import logger
import random
from typing import Union, Optional, Callable, Awaitable, Dict, Tuple

from aiogram import Bot
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

from app.constants import ALL_STAGES  # (для анимаций)
from db.db_users import UserRepo  # (для обновления can_send_msg)


# --- Функции UI (Анимации) ---
# (Они не связаны с отправкой, но лежат здесь для удобства)

async def animate_prediction(target: Message):
    """Показываем 3 этапа «мистики»."""
    try:
        stages = random.sample(ALL_STAGES, 3)
        msg = await target.answer(stages[0])
        for stage in stages[1:]:
            await asyncio.sleep(1.0)
            await msg.edit_text(stage)
        await asyncio.sleep(1.0)
        await msg.delete()
    except Exception as e:
        logger.error(f"Ошибка в animate_prediction: {e}")


async def animate_wisdom(target: Message):
    """Показываем три «мистических» кадра."""
    frames = ["⏳", "⌛️", "⏳"]
    base = "Листаю свитки древней иронии"
    try:
        msg = await target.answer(f"{base}... {frames[0]}")
        for e in frames[1:]:
            await asyncio.sleep(0.5)
            await msg.edit_text(f"{base}... {e}")
        await asyncio.sleep(1.0)
        await msg.delete()
    except Exception as e:
        logger.error(f"Ошибка в animate_wisdom: {e}")


# --- Функции безопасной отправки ---

async def safe_send_message(
    bot: Bot,
    user_id: int,
    text: str,
    user_repo: Optional[UserRepo] = None,
    reply_markup: Union[ReplyKeyboardMarkup, InlineKeyboardMarkup, None] = None,
    reply_to_message_id: Optional[int] = None
) -> bool:
    """
    Безопасно отправляет текстовое сообщение (включая ответы).
    - При успехе возвращает True.
    - При 'FloodWait' ждет и пытается снова.
    - При 'Forbidden' (блок) обновляет user_repo и возвращает False.
    - При других ошибках возвращает False.
    """
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup, reply_to_message_id=reply_to_message_id)
        return True
    except TelegramRetryAfter as e:
        logger.warning(f"Flood control: {e.retry_after} сек. для user {user_id}. Спим...")
        await asyncio.sleep(e.retry_after + 0.1)
        # Рекурсия: передаем все аргументы
        return await safe_send_message(bot, user_id, text, user_repo, reply_markup, reply_to_message_id)
    except TelegramForbiddenError:
        logger.warning(f"Пользователь {user_id} заблокировал бота.")
        if user_repo:
            await user_repo.update_user_profile_parameters(user_id, can_send_msg=False)
            logger.info(f"User {user_id} обновлен: can_send_msg=False.")
        return False
    except (TelegramBadRequest, Exception) as e:
        logger.error(f"Ошибка отправки сообщения (safe_send_message) {user_id}: {e}")
        return False



async def safe_send_photo(
        bot: Bot,
        chat_id: int,
        file_id: Optional[str],
        file_path: Optional[str],
        caption: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        user_repo: Optional[UserRepo] = None,  # Для 'blocked' статуса (в ЛС)
        reply_to_message_id: Optional[int] = None,
        # 👈 ГЛАВНОЕ: функция, которая обновит file_id в нужной таблице
        update_file_id_callback: Optional[Callable[[str], Awaitable[None]]] = None
) -> bool:
    """
    Универсальная функция отправки фото (для мемов, мудростей и т.д.).
    - Пытается отправить по file_id.
    - При неудаче (или отсутствии file_id) отправляет по file_path.
    - Если отправка по file_path прошла, вызывает update_file_id_callback.
    - Обрабатывает 'FloodWait' и 'Forbidden' (с обновлением БД).
    - Возвращает True (успех) или False (неудача).
    """

    # --- 1. Попытка по file_id ---
    if file_id:
        try:
            await bot.send_photo(chat_id, file_id, caption=caption, reply_markup=reply_markup,
                                 reply_to_message_id=reply_to_message_id)
            return True  # Успех, file_id актуален, выходим

        except TelegramRetryAfter as e:
            logger.warning(f"Flood control (file_id): {e.retry_after} сек. для {chat_id}. Спим...")
            await asyncio.sleep(e.retry_after + 0.1)
            # Рекурсия (снова пытаемся с file_id)
            return await safe_send_photo(bot, chat_id, file_id, file_path, caption, reply_markup, user_repo,
                                         reply_to_message_id, update_file_id_callback)

        except TelegramForbiddenError:
            logger.warning(f"Пользователь/чат {chat_id} заблокировал бота (file_id).")
            # Обновляем, только если это личный чат (chat_id > 0)
            if user_repo and chat_id > 0:
                await user_repo.update_user_profile_parameters(chat_id, can_send_msg=False)
            return False

        except (TelegramBadRequest, Exception) as e:
            # Ошибка! file_id плохой (или другая проблема).
            # Не выходим, а *продолжаем* к Попытке 2 (file_path).
            logger.warning(f"Bad file_id {file_id}: {e}. Пробую по file_path.")

    # --- 2. Фолбэк по file_path ---
    if file_path:
        try:
            sent_message = await bot.send_photo(
                chat_id, FSInputFile(file_path),
                caption=caption, reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id
            )

            # УСПЕХ! Теперь обновляем file_id в БД, если нужно
            if update_file_id_callback and sent_message and sent_message.photo:
                new_file_id = sent_message.photo[-1].file_id
                if new_file_id != file_id:  # Обновляем, только если ID новый/изменился
                    try:
                        logger.info(f"Обновление file_id для чата {chat_id} (из file_path).")
                        await update_file_id_callback(new_file_id)
                    except Exception as e:
                        logger.error(f"Ошибка при вызове update_file_id_callback: {e}")
            return True  # Успех

        except TelegramRetryAfter as e:
            logger.warning(f"Flood control (file_path): {e.retry_after} сек. для {chat_id}. Спим...")
            await asyncio.sleep(e.retry_after + 0.1)
            # Рекурсия (пытаемся снова, но *только* с file_path, file_id=None)
            return await safe_send_photo(
                bot, chat_id, None, file_path, caption, reply_markup,
                user_repo, reply_to_message_id, update_file_id_callback
            )

        except TelegramForbiddenError:
            logger.warning(f"Пользователь/чат {chat_id} заблокировал бота (file_path).")
            if user_repo and chat_id > 0:
                await user_repo.update_user_profile_parameters(chat_id, can_send_msg=False)
            return False

        except (TelegramBadRequest, Exception) as e:
            logger.error(f"Критическая ошибка отправки (file_path) {file_path}: {e}")
            return False  # Финальная неудача

    # --- 3. Провал ---
    # Мы здесь, если:
    # 1. Не был предоставлен ни file_id, ни file_path.
    # 2. Был плохой file_id, но не был предоставлен file_path для фолбэка.
    logger.error(f"Не удалось отправить фото в чат {chat_id}. Нет валидного источника.")
    return False



async def fetch_user_display_data(
        bot: Bot,
        user_id: int,
        db_user_data: Dict
) -> Tuple[str, str]:
    """
    Получает имя пользователя из БД (username) или из Telegram API (first_name)
    и формирует HTML-ссылку.
    Возвращает (имя для отображения, HTML-ссылка).

    Эта функция обеспечивает корректное отображение имени, даже если у пользователя
    нет username в БД (используется first_name, полученный через API).
    """
    username = db_user_data.get('username')

    if username:
        # 1. Есть username (самый быстрый путь)
        display_name = f"@{username}"
    else:
        # 2. Нет username (медленный путь: API call)
        try:
            # Получаем объект Chat (он же User)
            chat_member = await bot.get_chat(user_id)
            # Используем first_name, или user_id как крайний вариант
            display_name = chat_member.first_name or f"User {user_id}"
        except Exception:
            # Финальный запасной вариант, если API недоступно или не находит пользователя
            display_name = f"User {user_id}"

            # Формируем окончательную HTML-ссылку
    link = f"<a href='tg://user?id={user_id}'>{display_name}</a>"
    return display_name, link