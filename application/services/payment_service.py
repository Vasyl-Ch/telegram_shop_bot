"""
Payment Service — оркестрация платежей.

Координирует OrderService, провайдеры оплаты и уведомления.
"""

import asyncio
import logging
from typing import Optional

from domain.entities.order import Order
from domain.enums.payment_method import PaymentMethod
from domain.enums.order_status import OrderStatus
from application.services.order_service import OrderService
from application.services.notification_service import NotificationService
from infrastructure.payments.stripe_provider import StripeProvider
from infrastructure.payments.cash_provider import CashProvider
from infrastructure.payments.payment_provider import PaymentProviderError
from application.dto.order_dto import PaymentResultDTO, OrderResponseDTO
from utils.helpers import get_customer_name

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Сервис обработки платежей.

    Применение Strategy Pattern через PaymentProvider.
    """

    def __init__(
        self,
        order_service: OrderService,
        notification_service: NotificationService,
        stripe_provider: StripeProvider,
        cash_provider: CashProvider,
    ):
        """
        Args:
            order_service: Сервис заказов
            notification_service: Сервис уведомлений
            stripe_provider: Stripe провайдер
            cash_provider: COD провайдер
        """
        self._order_service = order_service
        self._notification = notification_service
        self._stripe = stripe_provider
        self._cash = cash_provider
        logger.info("✅ PaymentService initialized")

    def initiate_payment(self, order: Order) -> Optional[str]:
        """
        Инициирует платёж для заказа.

        Args:
            order: Заказ с выбранным способом оплаты

        Returns:
            Optional[str]: URL для оплаты (Stripe) или None (Cash)

        Raises:
            PaymentProviderError: При ошибке создания платежа
            ValueError: Если способ оплаты не выбран
        """
        if not order.payment_method:
            raise ValueError("Payment method not set")

        if order.payment_method == PaymentMethod.STRIPE:
            return self._initiate_stripe(order)

        if order.payment_method == PaymentMethod.CASH:
            self._initiate_cash(order)
            return None

        raise ValueError(f"Unknown payment method: {order.payment_method}")

    def _initiate_stripe(self, order: Order) -> str:
        """Создаёт Stripe Checkout Session."""
        try:
            payment_data = asyncio.run(self._stripe.create_payment(order))
            order.set_stripe_session(payment_data["payment_id"])

            logger.info(
                f"💳 Stripe session created for order #{order.order_id}"
            )
            return payment_data["payment_url"]

        except PaymentProviderError as e:
            logger.error(f"Stripe initiation failed: {e}")
            raise

    def _initiate_cash(self, order: Order) -> None:
        """Обрабатывает COD заказ."""
        asyncio.run(self._cash.create_payment(order))
        logger.info(f"💵 COD payment initiated for order #{order.order_id}")

    def check_stripe_payment(self, order: Order) -> PaymentResultDTO:
        """
        Проверяет статус Stripe платежа.

        Теперь возвращает PaymentResultDTO вместо bool —
        handler получает готовое сообщение и не знает
        про детали Stripe.

        Args:
            order: Заказ

        Returns:
            PaymentResultDTO: Результат с готовым сообщением
        """
        if not order.stripe_session_id:
            return PaymentResultDTO(
                order_id=order.order_id,
                is_paid=False,
                new_status=order.status,
                message_for_user="❌ Сессия оплаты не найдена.",
            )

        try:
            is_paid = asyncio.run(
                self._stripe.verify_payment(order.stripe_session_id)
            )

            if is_paid:
                details = asyncio.run(
                    self._stripe.get_payment_details(
                        order.stripe_session_id
                    )
                )
                updated_order = self._order_service.mark_as_paid(
                    order.order_id,
                    {
                        "payment_intent_id": details.get(
                            "payment_intent_id"
                        )
                    },
                )

                # ✅ ДОБАВИТЬ: Уведомляем продавца об оплате
                customer_name = get_customer_name(
                    self._notification._bot,
                    updated_order.chat_id
                )
                self._notification.notify_seller_payment_received(
                    updated_order,
                    customer_name
                )

                return PaymentResultDTO(
                    order_id=order.order_id,
                    is_paid=True,
                    new_status=updated_order.status,
                    message_for_user=(
                        f"✅ Оплата подтверждена!\n\n"
                        f"Заказ #{order.order_id} принят в обработку."
                    ),
                    updated_order_dto=OrderResponseDTO.from_order(
                        updated_order
                    ),
                    payment_intent_id=details.get("payment_intent_id"),
                )

            return PaymentResultDTO(
                order_id=order.order_id,
                is_paid=False,
                new_status=order.status,
                message_for_user=(
                    "⏳ Оплата ещё не поступила.\n"
                    "Попробуйте проверить через минуту."
                ),
            )

        except Exception as e:
            logger.error(
                f"Payment check error for order "
                f"#{order.order_id}: {e}"
            )
            return PaymentResultDTO(
                order_id=order.order_id,
                is_paid=False,
                new_status=order.status,
                message_for_user="❌ Ошибка проверки оплаты. Попробуйте позже.",
            )

    def handle_payment_success(self, order: Order, session_details: dict) -> None:
        """
        Callback для PaymentPoller при успешной оплате.

        Args:
            order: Заказ
            session_details: Детали Stripe сессии
        """
        try:
            updated = self._order_service.mark_as_paid(
                order.order_id,
                {"payment_intent_id": session_details.get("payment_intent_id")}
            )

            # ✅ Уведомляем покупателя
            self._notification.notify_order_status_changed(updated)

            # ✅ ДОБАВИТЬ: Уведомляем продавца об оплате
            customer_name = get_customer_name(
                self._notification._bot,
                updated.chat_id
            )
            self._notification.notify_seller_payment_received(
                updated,
                customer_name
            )

            logger.info(
                f"✅ Payment success handled for order #{order.order_id}"
            )
        except Exception as e:
            logger.error(f"handle_payment_success error: {e}")

    def handle_payment_failed(self, order: Order) -> None:
        """
        Callback для PaymentPoller при неудачной оплате.

        Args:
            order: Заказ
        """
        try:
            updated = self._order_service.cancel_order(
                order.order_id,
                reason="Платёж не прошёл или истёк срок"
            )
            self._notification.notify_order_status_changed(updated)
            logger.info(
                f"❌ Payment failed handled for order #{order.order_id}"
            )
        except Exception as e:
            logger.error(f"handle_payment_failed error: {e}")

