"""
Dependency Injection Container.

Centrally manage application-wide dependencies.
Uses the Service Locator pattern via dependency-injector.
"""

from dependency_injector import containers, providers

from application.services.statistics_service import StatisticsService
from infrastructure.external.google_sheets_client import GoogleSheetsClient
from infrastructure.repositories.order_repository import OrderRepository
from infrastructure.repositories.cart_repository import CartRepository
from infrastructure.repositories.catalog_repository import CatalogRepository
from infrastructure.payments.stripe_provider import StripeProvider
from infrastructure.payments.cash_provider import CashProvider
from infrastructure.payments.payment_poller import PaymentPoller

from application.services.order_service import OrderService
from application.services.cart_service import CartService
from application.services.payment_service import PaymentService
from application.services.notification_service import NotificationService
from infrastructure.repositories.user_limit_repository import UserLimitRepository


class Container(containers.DeclarativeContainer):
    """
    Application dependency container.

    Application of Dependency Injection Pattern:
    - Dependency Inversion (SOLID)
    - Centralized configuration
    - Easy replacement of implementations
    - Simplified testing
    """

    # ══════════════════════════════════════════════════════════════
    # Configuration
    # ══════════════════════════════════════════════════════════════

    config = providers.Configuration()

    # ══════════════════════════════════════════════════════════════
    # Infrastructure Layer - External Services
    # ══════════════════════════════════════════════════════════════

    google_sheets_client = providers.Singleton(
        GoogleSheetsClient,
        google_disk_id=config.google_disk_id,
        json_key_file=config.json_key_file,
    )

    # ══════════════════════════════════════════════════════════════
    # Infrastructure Layer - Repositories
    # ══════════════════════════════════════════════════════════════

    order_repository = providers.Singleton(
        OrderRepository,
        persistence_file="data/orders.json",
    )

    cart_repository = providers.Singleton(
        CartRepository,
    )

    catalog_repository = providers.Singleton(
        CatalogRepository,
        google_sheets_client=google_sheets_client,
    )

    user_limit_repository = providers.Singleton(
        UserLimitRepository,
        persistence_file="data/user_limits.json",
    )

    # ══════════════════════════════════════════════════════════════
    # Infrastructure Layer - Payment Providers
    # ══════════════════════════════════════════════════════════════

    stripe_provider = providers.Singleton(
        StripeProvider,
    )

    cash_provider = providers.Singleton(
        CashProvider,
    )

    # ══════════════════════════════════════════════════════════════
    # Application Layer - Services
    # ══════════════════════════════════════════════════════════════

    order_service = providers.Singleton(
        OrderService,
        order_repository=order_repository,
        catalog_repository=catalog_repository,
    )

    cart_service = providers.Singleton(
        CartService,
        cart_repo=cart_repository,
        catalog_repo=catalog_repository,
    )

    notification_service = providers.Singleton(
        NotificationService,
        bot=providers.Object(None),
        seller_chat_id=config.seller_chat_id,
    )

    payment_service = providers.Singleton(
        PaymentService,
        order_service=order_service,
        notification_service=notification_service,
        stripe_provider=stripe_provider,
        cash_provider=cash_provider,
    )

    statistics_service = providers.Singleton(
        StatisticsService,
        order_repository=order_repository,
    )

    # ══════════════════════════════════════════════════════════════
    # Infrastructure Layer - Payment Poller
    # ══════════════════════════════════════════════════════════════

    payment_poller = providers.Singleton(
        PaymentPoller,
        stripe_provider=stripe_provider,
        order_service=order_service,
        payment_service=payment_service,
        poll_interval=config.payment_poll_interval,
        max_age_hours=config.payment_max_age_hours,
    )
