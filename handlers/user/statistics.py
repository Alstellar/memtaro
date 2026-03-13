# handlers/user/statistics.py
from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ChatType

from db.db_users import UserRepo
from db.db_statistics import StatisticsRepo
from db.db_images import ImageRepo
from app.services.safe_sender import safe_send_message
from app.services.user_service import ensure_user_records, get_profile_service
from db.db_predicts import PredictRepo  # Нужно для ensure_user_records

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text == "📊 Статистика")
async def user_statistics_handler(
        message: Message,
        bot: Bot,
        user_repo: UserRepo,
        stats_repo: StatisticsRepo,
        image_repo: ImageRepo,
        predict_repo: PredictRepo
):
    user_id = message.from_user.id

    # Получаем ProfileService
    profile_service = get_profile_service(user_repo, stats_repo)

    # Обновляем активность пользователя
    await profile_service.update_user_activity(user_id)

    # Обновляем юзернейм, если он изменился
    username = message.from_user.username
    if username:
        current_user = await user_repo.get_user(user_id)
        if current_user and current_user.get("username") != username:
            await user_repo.update_user_profile_parameters(user_id, username=username)

    # Увеличиваем внутреннюю активность
    await profile_service.increment_internal_activity(user_id)

    # Гарантируем, что запись в stats существует
    await ensure_user_records(user_id, predict_repo, stats_repo)

    stats = await stats_repo.get_statistics_entry(user_id)

    # Получаем просмотры мемов, загруженных пользователем
    mem_views = await image_repo.get_user_mem_views(user_id)
    user_images_count = await image_repo.get_images_statistics_by_user_id(user_id)

    text = (
        "<b>📊 Ваша статистика:</b>\n\n"
        f"✨ Потрачено кармы: <code>{stats.get('spent_karma', 0)}</code>\n\n"
        f"🖼 Количество добавленных мемов: <code>{user_images_count}</code>\n"
        f"🔮 Получено мем-предсказаний: <code>{stats.get('count_received_memepredictions', 0)}</code>\n"
        f"👀 Просмотрено ваших мемов за месяц: <code>{mem_views['watch_month']}</code>\n"
        f"👀 Просмотрено ваших мемов за все время: <code>{mem_views['watch_all']}</code>\n\n"
        f"🧙‍♂️ Получено Мудростей дня: <code>{stats.get('count_received_wisdoms', 0)}</code>"
    )

    await safe_send_message(bot, user_id, text)