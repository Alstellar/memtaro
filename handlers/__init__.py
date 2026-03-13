from aiogram import Dispatcher, Router

# Импортируем роутеры
from .user import start as user_start_router
from .user import prediction as user_prediction_router
from .user import menu as user_menu_router
from .user import profile as user_profile_router
from .user import karma as user_karma_router
from .user import theme as user_theme_router
from .user import referral as user_referral_router
from .user import statistics as user_statistics_router
from .user import upload_meme as user_upload_router
from .user import marketplace as user_marketplace_router

from .admin import system as admin_system_router
from .admin import statistics as admin_statistics_router
from .admin import moderation as admin_moderation_router
from .admin import mailing as admin_mailing_router
from .admin import settings as admin_settings_router

from .group import prediction as group_prediction_router
from .group import activity_tracker as group_activity_router



def register_all_handlers(dp: Dispatcher):
    """
    Регистрирует все хэндлеры (роутеры) в главном Dispatcher.
    """
    # Создаем главный "супер-роутер"
    main_router = Router()

    # Admin handlers
    main_router.include_router(admin_system_router.router)
    main_router.include_router(admin_statistics_router.router)
    main_router.include_router(admin_moderation_router.router)
    main_router.include_router(admin_mailing_router.router)
    main_router.include_router(admin_settings_router.router)

    # Подключаем роутеры
    main_router.include_router(user_start_router.router)
    main_router.include_router(user_prediction_router.router)
    main_router.include_router(user_menu_router.router)
    main_router.include_router(user_profile_router.router)
    main_router.include_router(user_karma_router.router)
    main_router.include_router(user_theme_router.router)
    main_router.include_router(user_referral_router.router)
    main_router.include_router(user_statistics_router.router)
    main_router.include_router(user_upload_router.router)
    main_router.include_router(user_marketplace_router.router)

    main_router.include_router(group_activity_router.router)
    main_router.include_router(group_prediction_router.router)


    # Регистрируем "супер-роутер" в Dispatcher
    # `include_router` регистрирует все хэндлеры, которые мы в него "включили"
    dp.include_router(main_router)
