"""
The entry point of the application.

Composition Root – This is where all dependencies are created
and communicate together via DI Container.

Launch structure:
1. Loading the config
2. Creating a DI Container
3. Creating and configuring a bot
4. Registration handlers
5. Running polling + background workers
"""

import logging
import threading
import time
import telebot
import os

from config import containers
from config.settings import settings
from config.containers import Container
from presentation.middleware.ban_check_middleware import BanCheckMiddleware
from utils.logger import setup_logging

from presentation.handlers.start_handler import register_start_handlers
from presentation.handlers.catalog_handler import register_catalog_handlers
from presentation.handlers.cart_handler import register_cart_handlers
from presentation.handlers.checkout_handler import register_checkout_handlers
from presentation.handlers.seller_handler import register_seller_handlers

from presentation.middleware.logging_middleware import LoggingMiddleware
from presentation.middleware.rate_limit_middleware import RateLimitMiddleware


def create_bot() -> telebot.TeleBot:
    """
    Creates and configures a bot instance.

    Returns:
        telebot. TeleBot: Customized Bot
    """
    bot = telebot.TeleBot(
        token=settings.bot_token,
        parse_mode=None,
        threaded=True,
        use_class_middlewares=True,
    )

    bot.setup_middleware(LoggingMiddleware())
    bot.setup_middleware(RateLimitMiddleware(max_requests=10, time_window=10))
    bot.setup_middleware(
        BanCheckMiddleware(containers.Container.user_limit_repository())
    )

    return bot


def setup_container() -> Container:
    """
    Creates and configures a DI Container.

    Returns:
        Container: Configured dependency container
    """
    logger = logging.getLogger(__name__)
    logger.info("🔧 Setting up DI Container...")

    container = Container()

    container.config.from_dict(
        {
            "google_disk_id": settings.google_disk_id,
            "json_key_file": settings.json_key_file,
            "seller_chat_id": settings.seller_chat_id,
            "payment_poll_interval": settings.payment_poll_interval,
            "payment_max_age_hours": settings.payment_max_age_hours,
        }
    )

    logger.info("✅ DI Container configured")

    return container


def register_all_handlers(bot: telebot.TeleBot, container: Container) -> None:
    """
    Registers all handlers of the bot.

    Args:
        bot: Bot instance
        container: DI container
    """
    logger = logging.getLogger(__name__)

    # ════════════════════════════════════════════════════════════
    # Basic handlers
    # ════════════════════════════════════════════════════════════

    register_start_handlers(bot)

    # ════════════════════════════════════════════════════════════
    # Catalog
    # ════════════════════════════════════════════════════════════

    register_catalog_handlers(
        bot=bot,
        catalog_repo=container.catalog_repository(),
        cart_repo=container.cart_repository(),
    )

    # ════════════════════════════════════════════════════════════
    # Cart
    # ════════════════════════════════════════════════════════════

    register_cart_handlers(
        bot=bot,
        cart_repo=container.cart_repository(),
        catalog_repo=container.catalog_repository(),
    )

    # ════════════════════════════════════════════════════════════
    # Checkout (placing an order)
    # ════════════════════════════════════════════════════════════

    register_checkout_handlers(
        bot=bot,
        order_service=container.order_service(),
        payment_service=container.payment_service(),
        cart_repo=container.cart_repository(),
        order_repo=container.order_repository(),
        seller_chat_id=settings.seller_chat_id,
    )

    # ════════════════════════════════════════════════════════════
    # Seller panel (Seller Panel)
    # ════════════════════════════════════════════════════════════

    register_seller_handlers(
        bot=bot,
        order_service=container.order_service(),
        order_repo=container.order_repository(),
        seller_chat_id=settings.seller_chat_id,
        catalog_repo=container.catalog_repository(),
        user_limit_repo=container.user_limit_repository(),
    )

    logger.info("✅ All handlers registered")


def start_background_workers(container: Container) -> None:
    """
    Starts background workers.

    Args:
        container: DI container
    """
    logger = logging.getLogger(__name__)

    # ════════════════════════════════════════════════════════════
    # Payment Poller (Stripe polling)
    # ════════════════════════════════════════════════════════════

    poller = container.payment_poller()
    poller.start()
    logger.info("🚀 Payment poller started")

    # ════════════════════════════════════════════════════════════
    # Catalog Auto-Reload (every 5 minutes)
    # ════════════════════════════════════════════════════════════

    def auto_reload_catalog():
        """Background worker for auto-updating the directory."""
        catalog_repo = container.catalog_repository()

        while True:
            time.sleep(300)
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

    # ════════════════════════════════════════════════════════════
    # Daily Statistics Worker (send at 9:00 am)
    # ════════════════════════════════════════════════════════════

    def daily_statistics_worker():
        """Background worker to send daily statistics."""
        statistics_service = container.statistics_service()
        notification_service = container.notification_service()

        import time
        from datetime import datetime, timedelta

        last_sent_date = None

        while True:
            try:
                now = datetime.now()

                if now.hour == 9 and 0 <= now.minute < 5:
                    current_date = now.date()

                    if last_sent_date != current_date:
                        yesterday = now - timedelta(days=1)
                        stats = statistics_service.get_daily_statistics(yesterday)

                        if stats.get("has_changes"):
                            message = statistics_service.format_daily_statistics(stats)
                            if message:
                                notification_service._bot.send_message(
                                    notification_service._seller_chat_id,
                                    message,
                                    parse_mode="HTML",
                                )
                                logger.info(
                                    f"📊 Daily statistics sent for {stats['date']}"
                                )
                        else:
                            logger.info(
                                f"📊 No changes for {stats['date']}, skipping statistics"
                            )

                        last_sent_date = current_date

                time.sleep(60)

            except Exception as e:
                logger.error(f"❌ Daily statistics worker error: {e}", exc_info=True)
                time.sleep(60)

    statistics_thread = threading.Thread(
        target=daily_statistics_worker,
        name="DailyStatistics",
        daemon=True,
    )
    statistics_thread.start()
    logger.info("📊 Daily statistics worker started")

    # ════════════════════════════════════════════════════════════
    # Low Stock Check Worker (checked every 6 hours)
    # ════════════════════════════════════════════════════════════

    def low_stock_check_worker():
        """Background worker для проверки низких остатков."""
        catalog_repo = container.catalog_repository()
        notification_service = container.notification_service()

        notified_products = set()

        while True:
            try:
                low_stock_products = catalog_repo.get_low_stock_products(threshold=5)

                for product in low_stock_products:
                    if product.product_id not in notified_products:
                        notification_service.notify_low_stock(
                            product.name, product.stock
                        )
                        notified_products.add(product.product_id)
                        logger.info(
                            f"⚠️ Low stock notification sent for {product.name}"
                        )

                current_low_stock_ids = {p.product_id for p in low_stock_products}
                notified_products.intersection_update(current_low_stock_ids)

                time.sleep(21600)

            except Exception as e:
                logger.error(f"❌ Low stock check worker error: {e}", exc_info=True)
                time.sleep(21600)

    low_stock_thread = threading.Thread(
        target=low_stock_check_worker,
        name="LowStockCheck",
        daemon=True,
    )
    low_stock_thread.start()
    logger.info("⚠️ Low stock check worker started")


def ensure_data_directory():
    """
    Creates a data/ directory to store persistence files.
    """
    os.makedirs("data", exist_ok=True)


def main() -> None:
    """The entry point of the application."""

    # ════════════════════════════════════════════════════════════
    # 1. Setting up logging
    # ════════════════════════════════════════════════════════════

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("🚀 Starting Telegram Shop Bot")
    logger.info(f"🌍 Environment: {settings.environment}")
    logger.info(f"📊 Log Level: {settings.log_level}")
    logger.info("=" * 60)

    # ════════════════════════════════════════════════════════════
    # 2. Creating a directory for data
    # ════════════════════════════════════════════════════════════

    ensure_data_directory()

    # ════════════════════════════════════════════════════════════
    # 3. Creating a DI Container
    # ════════════════════════════════════════════════════════════

    container = setup_container()

    # ════════════════════════════════════════════════════════════
    # 4. Creating a bot
    # ════════════════════════════════════════════════════════════

    bot = create_bot()

    # ════════════════════════════════════════════════════════════
    # 5. Inject the bot into NotificationService
    # ════════════════════════════════════════════════════════════

    notification_service = container.notification_service()
    notification_service._bot = bot

    logger.info("✅ Bot instance injected into NotificationService")

    # ════════════════════════════════════════════════════════════
    # 6. Registering handlers
    # ════════════════════════════════════════════════════════════

    register_all_handlers(bot, container)

    # ════════════════════════════════════════════════════════════
    # 7. Running background workers
    # ════════════════════════════════════════════════════════════

    start_background_workers(container)

    # ════════════════════════════════════════════════════════════
    # 8. Running the bot
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

        poller = container.payment_poller()
        poller.stop()

        logger.info("👋 Goodbye!")


if __name__ == "__main__":
    main()
