"""
Payment Service — payment orchestration.

Coordinates OrderService, payment providers, and notifications.
"""

import asyncio
import logging
from typing import Optional

from domain.entities.order import Order
from domain.enums.payment_method import PaymentMethod
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
    Payment processing service.

    Applying the Strategy Pattern through the PaymentProvider.
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
            order_service: Order Service
            notification_service: Notification Service
            stripe_provider: Stripe provider
            cash_provider: COD provider
        """
        self._order_service = order_service
        self._notification = notification_service
        self._stripe = stripe_provider
        self._cash = cash_provider
        logger.info("✅ PaymentService initialized")

    def initiate_payment(self, order: Order) -> Optional[str]:
        """
        Initiates payment for the order.

        Args:
            order: Order with the selected payment method

        Returns:
            Optional[str]: URL for payment (Stripe) or None (Cash)

        Raises:
            PaymentProviderError: On payment creation error
            ValueError: If the payment method is not selected
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
        """Creates Stripe Checkout Session."""
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
        """Processes the COD order."""
        asyncio.run(self._cash.create_payment(order))
        logger.info(f"💵 COD payment initiated for order #{order.order_id}")

    def check_stripe_payment(self, order: Order) -> PaymentResultDTO:
        """
        Checks the status of the Stripe payment.

        Now returns PaymentResultDTO instead of bool —
        handler receives the finished message and does not know
        about Stripe details.

        Args:
            order: Order

        Returns:
            PaymentResultDTO: Result with a ready-made message
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
        Callback for PaymentPoller upon successful payment.

        Args:
            order: Order
            session_details: Stripe Session Details
        """
        try:
            updated = self._order_service.mark_as_paid(
                order.order_id,
                {"payment_intent_id": session_details.get("payment_intent_id")}
            )

            self._notification.notify_order_status_changed(updated)

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
        Callback for PaymentPoller in case of unsuccessful payment.

        Args:
            order: Order
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
