"""
Точка входа приложения.

Composition Root — здесь создаются все зависимости
и связываются воедино через DI Container.

Структура запуска:
1. Загрузка конфига
2. Создание DI Container
3. Создание и настройка бота
4. Регистрация handlers
5. Запуск polling + background workers
"""

import logging
import threading
import time
import telebot
import os

from config.settings import settings
from config.containers import Container
from utils.logger import setup_logging

# Presentation Handlers
from presentation.handlers.start_handler import register_start_handlers
from presentation.handlers.catalog_handler import register_catalog_handlers
from presentation.handlers.cart_handler import register_cart_handlers
from presentation.handlers.checkout_handler import register_checkout_handlers
from presentation.handlers.seller_handler import register_seller_handlers

# Middleware
from presentation.middleware.logging_middleware import LoggingMiddleware
from presentation.middleware.rate_limit_middleware import RateLimitMiddleware


def create_bot() -> telebot.TeleBot:
    """
    Создаёт и конфигурирует инстанс бота.

    Returns:
        telebot.TeleBot: Настроенный бот
    """
    bot = telebot.TeleBot(
        token=settings.bot_token,
        parse_mode=None,
        threaded=True,
        use_class_middlewares=True,
    )

    # ✅ Подключаем middleware
    bot.setup_middleware(LoggingMiddleware())
    bot.setup_middleware(
        RateLimitMiddleware(
            max_requests=10,
            time_window=10
        )
    )

    return bot


def setup_container() -> Container:
    """
    Создаёт и настраивает DI Container.

    Returns:
        Container: Настроенный контейнер зависимостей
    """
    logger = logging.getLogger(__name__)
    logger.info("🔧 Setting up DI Container...")

    container = Container()

    # Загружаем конфигурацию из settings
    container.config.from_dict({
        'google_disk_id': settings.google_disk_id,
        'json_key_file': settings.json_key_file,
        'seller_chat_id': settings.seller_chat_id,
        'payment_poll_interval': settings.payment_poll_interval,
        'payment_max_age_hours': settings.payment_max_age_hours,
    })

    logger.info("✅ DI Container configured")

    return container


def register_all_handlers(bot: telebot.TeleBot, container: Container) -> None:
    """
    Регистрирует все handlers бота.

    Args:
        bot: Инстанс бота
        container: DI контейнер
    """
    logger = logging.getLogger(__name__)

    # ════════════════════════════════════════════════════════════
    # Базовые handlers
    # ════════════════════════════════════════════════════════════

    register_start_handlers(bot)

    # ════════════════════════════════════════════════════════════
    # Каталог
    # ════════════════════════════════════════════════════════════

    register_catalog_handlers(
        bot=bot,
        catalog_repo=container.catalog_repository(),
        cart_repo=container.cart_repository(),
    )

    # ════════════════════════════════════════════════════════════
    # Корзина
    # ════════════════════════════════════════════════════════════

    register_cart_handlers(
        bot=bot,
        cart_repo=container.cart_repository(),
        catalog_repo=container.catalog_repository(),
    )

    # ════════════════════════════════════════════════════════════
    # Checkout (оформление заказа)
    # ════════════════════════════════════════════════════════════

    register_checkout_handlers(
        bot=bot,
        order_service=container.order_service(),
        payment_service=container.payment_service(),
        cart_repo=container.cart_repository(),
        order_repo=container.order_repository(),
        stripe_provider=container.stripe_provider(),
        cash_provider=container.cash_provider(),
        seller_chat_id=settings.seller_chat_id,
    )

    # ════════════════════════════════════════════════════════════
    # Seller panel (панель продавца)
    # ════════════════════════════════════════════════════════════

    register_seller_handlers(
        bot=bot,
        order_service=container.order_service(),
        order_repo=container.order_repository(),
        seller_chat_id=settings.seller_chat_id,
        catalog_repo=container.catalog_repository(),
    )

    logger.info("✅ All handlers registered")


def start_background_workers(container: Container) -> None:
    """
    Запускает фоновые workers.

    Args:
        container: DI контейнер
    """
    logger = logging.getLogger(__name__)

    # ════════════════════════════════════════════════════════════
    # Payment Poller (Stripe polling)
    # ════════════════════════════════════════════════════════════

    poller = container.payment_poller()
    poller.start()
    logger.info("🚀 Payment poller started")

    # ════════════════════════════════════════════════════════════
    # Catalog Auto-Reload (каждые 5 минут)
    # ════════════════════════════════════════════════════════════

    def auto_reload_catalog():
        """Фоновый worker для автообновления каталога."""
        catalog_repo = container.catalog_repository()

        while True:
            time.sleep(300)  # 5 минут
            try:
                catalog_repo.reload()
                logger.info("🔄 Catalog auto-reloaded")
            except Exception as e:
                logger.error(f"❌ Auto-reload error: {e}")

    reload_thread = threading.Thread(
        target=auto_reload_catalog,
        name="CatalogReloader",
        daemon=True,
    )
    reload_thread.start()
    logger.info("🔄 Catalog auto-reload worker started")


def ensure_data_directory():
    """
    Создаёт директорию data/ для хранения persistence файлов.
    """
    os.makedirs('data', exist_ok=True)


def main() -> None:
    """Точка входа приложения."""

    # ════════════════════════════════════════════════════════════
    # 1. Настройка логирования
    # ════════════════════════════════════════════════════════════

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("🚀 Starting Telegram Shop Bot")
    logger.info(f"🌍 Environment: {settings.environment}")
    logger.info(f"📊 Log Level: {settings.log_level}")
    logger.info("=" * 60)

    # ════════════════════════════════════════════════════════════
    # 2. Создание директории для данных
    # ════════════════════════════════════════════════════════════

    ensure_data_directory()

    # ════════════════════════════════════════════════════════════
    # 3. Создание DI Container
    # ════════════════════════════════════════════════════════════

    container = setup_container()

    # ════════════════════════════════════════════════════════════
    # 4. Создание бота
    # ════════════════════════════════════════════════════════════

    bot = create_bot()

    # ════════════════════════════════════════════════════════════
    # 5. Инжектим бота в NotificationService
    # ════════════════════════════════════════════════════════════

    # NotificationService создан с bot=None в контейнере,
    # теперь обновляем его
    notification_service = container.notification_service()
    notification_service._bot = bot

    logger.info("✅ Bot instance injected into NotificationService")

    # ════════════════════════════════════════════════════════════
    # 6. Регистрация handlers
    # ════════════════════════════════════════════════════════════

    register_all_handlers(bot, container)

    # ════════════════════════════════════════════════════════════
    # 7. Запуск фоновых workers
    # ════════════════════════════════════════════════════════════

    start_background_workers(container)

    # ════════════════════════════════════════════════════════════
    # 8. Запуск бота
    # ════════════════════════════════════════════════════════════

    logger.info("✅ Bot is ready. Press Ctrl+C to stop.")
    logger.info("=" * 60)

    try:
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=5,
            logger_level=logging.WARNING,
        )
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}", exc_info=True)
    finally:
        # ════════════════════════════════════════════════════════
        # Graceful Shutdown
        # ════════════════════════════════════════════════════════

        logger.info("🔄 Shutting down gracefully...")

        # Останавливаем payment poller
        poller = container.payment_poller()
        poller.stop()

        logger.info("👋 Goodbye!")


if __name__ == "__main__":
    main()