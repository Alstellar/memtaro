# handlers/admin/statistics.py
from datetime import datetime
from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.enums import ChatType

from app.config import BotSettings
from db.db_statistics import StatisticsRepo
from db.db_images import ImageRepo
from db.db_users import UserRepo
from db.db_predicts import PredictRepo
from app.services.safe_sender import safe_send_message

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

# Фильтр: только админы
router.message.filter(lambda msg: msg.from_user.id in BotSettings().ADMIN_IDS)


@router.message(F.text == "📊 Общая статистика")
async def admin_global_statistics_handler(
        message: Message,
        bot: Bot,
        stats_repo: StatisticsRepo,
        image_repo: ImageRepo,
        user_repo: UserRepo,
        predict_repo: PredictRepo
):
    user_id = message.from_user.id

    # 1. Общая статистика (user_id=1)
    global_stats = await stats_repo.get_statistics_entry(1)
    if not global_stats:
        await safe_send_message(bot, user_id, "Общая статистика пока недоступна.")
        return

    # 2. Активность пользователей
    user_ids = await user_repo.get_all_user_ids()
    total_users = len(user_ids)

    today = datetime.now().date()
    count_today = 0
    count_week = 0
    count_month = 0

    # В оригинале был цикл по всем юзерам. При 1000+ юзерах это будет медленно.
    # Но пока оставляем оригинальную логику, позже можно оптимизировать через SQL COUNT
    for uid in user_ids:
        predict = await predict_repo.get_predicts(uid)
        if predict and predict.get('last_predict_date'):
            last_date = predict['last_predict_date']
            if last_date == today:
                count_today += 1
            days_diff = (today - last_date).days
            if days_diff < 7:
                count_week += 1
            if days_diff < 30:
                count_month += 1

    # 3. Статистика картинок
    # admin_id для исключения (берем первого админа из настроек)
    first_admin_id = BotSettings().ADMIN_IDS[0]
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
        f"Получили мем сегодня: <code>{count_today}</code>\n"
        f"Получили мем за 7 дней: <code>{count_week}</code>\n"
        f"Получили мем за 30 дней: <code>{count_month}</code>\n"
    )

    await safe_send_message(bot, user_id, text)