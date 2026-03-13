# handlers/admin/statistics.py
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.config import settings
from app.services.safe_sender import safe_send_message
from db.db_images import ImageRepo
from db.db_predicts import PredictRepo
from db.db_statistics import StatisticsRepo
from db.db_users import UserRepo

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.message.filter(lambda msg: msg.from_user.id in settings.bot.ADMIN_IDS)


@router.message(F.text == "📊 Общая статистика")
async def admin_global_statistics_handler(
    message: Message,
    bot: Bot,
    stats_repo: StatisticsRepo,
    image_repo: ImageRepo,
    user_repo: UserRepo,
    predict_repo: PredictRepo,
):
    user_id = message.from_user.id

    global_stats = await stats_repo.get_statistics_entry(1)
    if not global_stats:
        await safe_send_message(bot, user_id, "Общая статистика пока недоступна.")
        return

    total_users = await user_repo.count_users()
    activity = await predict_repo.get_predict_activity_summary()

    first_admin_id = settings.bot.ADMIN_IDS[0] if settings.bot.ADMIN_IDS else 0
    img_stats = await image_repo.get_images_statistics(first_admin_id)
    img_views = await image_repo.get_overall_image_views()

    text = (
        "<b>📊 Общая статистика бота:</b>\n\n"
        f"✨ Потрачено кармы: <code>{global_stats.get('spent_karma', 0)}</code>\n\n"
        f"🖼 Всего мемов: <code>{img_stats['total_images']}</code>\n"
        f"🖼 Пользовательских мемов: <code>{img_stats['user_images']}</code>\n\n"
        f"🔮 Получено мем-предсказаний: <code>{global_stats.get('count_received_memepredictions', 0)}</code>\n"
        f"🧙‍♂️ Получено Мудростей дня: <code>{global_stats.get('count_received_wisdoms', 0)}</code>\n"
        f"👀 Просмотрено мемов за месяц: <code>{img_views['watch_month']}</code>\n"
        f"👀 Просмотрено мемов за все время: <code>{img_views['watch_all']}</code>\n\n"
        "<b>👥 Статистика пользователей:</b>\n\n"
        f"Общее количество пользователей: <code>{total_users}</code>\n"
        f"Получили мем сегодня: <code>{activity['count_today']}</code>\n"
        f"Получили мем за 7 дней: <code>{activity['count_week']}</code>\n"
        f"Получили мем за 30 дней: <code>{activity['count_month']}</code>\n"
    )

    await safe_send_message(bot, user_id, text)
