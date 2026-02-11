"""
Payment Poller - фоновый worker для проверки статусов платежей.

Архитектура:
- Запускается в отдельном потоке
- Проверяет pending Stripe платежи каждые 60 секунд
- Обновляет статусы и уведомляет пользователей
- Graceful shutdown
- Не теряет платежи даже при сбоях

Применение SOLID:
- Single Responsibility: только polling платежей
- Dependency Injection: получает зависимости через конструктор
- Interface Segregation: использует callback'и для уведомлений
"""

import asyncio
import logging
from typing import List, Callable, Optional
from datetime import datetime, timedelta
import threading

from domain.entities.order import Order
from infrastructure.payments.stripe_provider import StripeProvider

logger = logging.getLogger(__name__)


class PaymentPoller:
    """
    Polling service для проверки статусов Stripe платежей.

    Почему отдельный класс:
    - Single Responsibility (только polling)
    - Легко тестировать
    - Можно заменить на Celery/RQ в будущем
    - Изолированная логика
    """

    def __init__(
            self,
            stripe_provider: StripeProvider,
            get_pending_orders: Callable[[], List[Order]],
            on_payment_success: Callable[[Order, dict], None],
            on_payment_failed: Callable[[Order], None],
            poll_interval: int = 60,  # секунды между проверками
            max_age_hours: int = 24,  # не проверять заказы старше X часов
    ):
        """
        Инициализация poller'а.

        Args:
            stripe_provider: Инстанс Stripe провайдера
            get_pending_orders: Функция для получения pending заказов
            on_payment_success: Callback при успешной оплате
            on_payment_failed: Callback при неудачной оплате
            poll_interval: Интервал проверки (секунды)
            max_age_hours: Максимальный возраст заказа для проверки
        """
        self.stripe_provider = stripe_provider
        self.get_pending_orders = get_pending_orders
        self.on_payment_success = on_payment_success
        self.on_payment_failed = on_payment_failed
        self.poll_interval = poll_interval
        self.max_age_hours = max_age_hours

        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(
            f"✅ PaymentPoller initialized "
            f"(interval: {poll_interval}s, max_age: {max_age_hours}h)"
        )

    def start(self) -> None:
        """
        Запускает poller в фоновом потоке.

        Безопасно вызывать несколько раз - проверяет _running флаг.
        """
        if self._running:
            logger.warning("⚠️ PaymentPoller already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="PaymentPoller",
            daemon=True
        )
        self._thread.start()

        logger.info(f"🚀 PaymentPoller started (interval: {self.poll_interval}s)")

    def stop(self) -> None:
        """
        Останавливает poller (graceful shutdown).

        Ждет завершения текущей итерации (timeout 10 секунд).
        """
        if not self._running:
            logger.info("ℹ️ PaymentPoller already stopped")
            return

        logger.info("🛑 Stopping PaymentPoller...")
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

            if self._thread.is_alive():
                logger.warning("⚠️ PaymentPoller thread did not stop gracefully")
            else:
                logger.info("✅ PaymentPoller stopped")

    def is_running(self) -> bool:
        """
        Проверяет, запущен ли poller.

        Returns:
            bool: True если работает
        """
        return self._running

    def _run_loop(self) -> None:
        """
        Основной цикл polling.

        Использует asyncio.run для каждой итерации,
        чтобы работать с async методами провайдера.
        """
        logger.info("🔄 PaymentPoller loop started")

        while self._running:
            try:
                # Запускаем async проверку в новом event loop
                asyncio.run(self._check_pending_payments())

            except Exception as e:
                # Логируем ошибку, но не останавливаем poller
                logger.error(
                    f"❌ Error in polling loop: {e}",
                    exc_info=True
                )

            # Ждем следующую итерацию (прерываемо для быстрого shutdown)
            for _ in range(self.poll_interval):
                if not self._running:
                    break
                asyncio.run(asyncio.sleep(1))

        logger.info("🏁 PaymentPoller loop finished")

    async def _check_pending_payments(self) -> None:
        """
        Проверяет все pending платежи.

        Логика:
        1. Получает список pending Stripe заказов
        2. Фильтрует слишком старые
        3. Проверяет каждый через Stripe API
        4. Вызывает callbacks при изменении статуса
        """
        try:
            # Получаем pending заказы
            pending_orders = self.get_pending_orders()

            if not pending_orders:
                logger.debug("ℹ️ No pending payments to check")
                return

            logger.info(f"🔍 Checking {len(pending_orders)} pending payment(s)...")

            # Вычисляем cutoff time (заказы старше не проверяем)
            cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)

            checked_count = 0
            success_count = 0
            failed_count = 0

            for order in pending_orders:
                # Пропускаем слишком старые заказы
                if order.created_at < cutoff_time:
                    logger.debug(
                        f"⏭️ Skipping old order #{order.order_id} "
                        f"(created {order.created_at})"
                    )
                    continue

                # Пропускаем заказы без Stripe session
                if not order.stripe_session_id:
                    logger.warning(
                        f"⚠️ Order #{order.order_id} has no stripe_session_id"
                    )
                    continue

                # Проверяем конкретный заказ
                result = await self._check_single_order(order)

                if result == 'success':
                    success_count += 1
                elif result == 'failed':
                    failed_count += 1

                checked_count += 1

                # Небольшая задержка между проверками (rate limiting)
                await asyncio.sleep(0.5)

            logger.info(
                f"✅ Checked {checked_count} order(s): "
                f"{success_count} success, {failed_count} failed"
            )

        except Exception as e:
            logger.error(
                f"❌ Error in _check_pending_payments: {e}",
                exc_info=True
            )

    async def _check_single_order(self, order: Order) -> Optional[str]:
        """
        Проверяет статус одного заказа.

        Args:
            order: Заказ для проверки

        Returns:
            Optional[str]: 'success', 'failed', или None (no change)
        """
        try:
            session_id = order.stripe_session_id

            logger.debug(f"🔍 Checking order #{order.order_id}, session: {session_id}")

            # Получаем детали сессии
            session_details = await self.stripe_provider.get_payment_details(
                session_id
            )

            if not session_details:
                logger.warning(
                    f"⚠️ Could not retrieve session for order #{order.order_id}"
                )
                return None

            payment_status = session_details['payment_status']

            if self._is_session_expired(order, session_details):
                if payment_status != 'paid':
                    logger.warning(f"⏰ Session EXPIRED for order #{order.order_id}")
                    try:
                        self.on_payment_failed(order)
                        return 'failed'
                    except Exception as e:
                        logger.error(f"Error in on_payment_failed callback: {e}", exc_info=True)
                        return None

            # Обработка успешной оплаты
            if payment_status == 'paid':
                logger.info(
                    f"✅ Payment SUCCESS for order #{order.order_id}"
                )

                # Вызываем callback (обработка в application layer)
                try:
                    self.on_payment_success(order, session_details)
                    return 'success'
                except Exception as e:
                    logger.error(
                        f"❌ Error in on_payment_success callback: {e}",
                        exc_info=True
                    )
                    return None

            # Обработка неудачной оплаты
            elif payment_status in ['unpaid']:
                # Проверяем, не истек ли срок сессии
                if self._is_session_expired(order, session_details):
                    logger.warning(
                        f"⏰ Payment EXPIRED for order #{order.order_id}"
                    )

                    try:
                        self.on_payment_failed(order)
                        return 'failed'
                    except Exception as e:
                        logger.error(
                            f"❌ Error in on_payment_failed callback: {e}",
                            exc_info=True
                        )
                        return None

            # Обработка отмененных платежей
            elif payment_status == 'canceled':
                logger.info(
                    f"❌ Payment CANCELLED for order #{order.order_id}"
                )

                try:
                    self.on_payment_failed(order)
                    return 'failed'
                except Exception as e:
                    logger.error(
                        f"❌ Error in on_payment_failed callback: {e}",
                        exc_info=True
                    )
                    return None

            return None

        except Exception as e:
            logger.error(
                f"❌ Error checking order #{order.order_id}: {e}",
                exc_info=True
            )
            return None

    def _is_session_expired(
            self,
            order: Order,
            session_details: dict
    ) -> bool:
        """
        Проверяет, истек ли срок Checkout Session.

        Args:
            order: Заказ
            session_details: Детали Stripe session

        Returns:
            bool: True если истек
        """
        # Проверяем expires_at из session
        expires_at = session_details.get('expires_at')
        if expires_at:
            current_timestamp = int(datetime.now().timestamp())
            return current_timestamp > expires_at

        # Fallback: проверяем по времени создания заказа
        # Session истекает через 4 часа после создания (наша настройка)
        expiration_time = order.created_at + timedelta(hours=4)
        return datetime.now() > expiration_time