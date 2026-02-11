"""
Stripe платежный провайдер (Checkout Session без webhook).

Особенности:
- Использует Stripe Checkout Session
- Не требует webhook URL
- Статус проверяется через polling
- Production-ready
"""

import stripe
from typing import Dict, Any, Optional
import logging

from infrastructure.payments.payment_provider import (
    PaymentProvider,
    PaymentProviderError
)
from domain.entities.order import Order
from config.settings import settings

logger = logging.getLogger(__name__)

# Инициализируем Stripe API
stripe.api_key = settings.stripe_secret_key


class StripeProvider(PaymentProvider):
    """
    Stripe Checkout Session реализация.

    Почему Checkout Session:
    - PCI DSS compliance из коробки
    - Готовый UI для оплаты
    - Автоматическая обработка 3D Secure
    - Встроенная обработка ошибок
    - Не требует frontend разработки
    """

    def __init__(self):
        """Инициализация провайдера."""
        # Success URL ведет обратно в Telegram
        self.success_url = f"https://t.me/{settings.bot_username}?start=payment_success"
        self.cancel_url = f"https://t.me/{settings.bot_username}?start=payment_cancelled"

        logger.info("✅ StripeProvider initialized (polling mode)")

    async def create_payment(self, order: Order) -> Dict[str, Any]:
        """
        Создает Stripe Checkout Session.

        Особенности:
        - Одноразовая сессия (expires_at через 4 часа)
        - Все данные заказа в metadata для recovery
        - Line items из заказа

        Args:
            order: Заказ для оплаты

        Returns:
            Dict с payment_url и session_id

        Raises:
            PaymentProviderError: при ошибке Stripe API
        """
        try:
            # Формируем line items для Stripe
            line_items = []
            for item in order.items:
                line_items.append({
                    'price_data': {
                        'currency': 'usd',  # Можно настроить через config
                        'unit_amount': int(item.price * 100),  # Цена в центах
                        'product_data': {
                            'name': item.name,
                            'description': f'Quantity: {item.quantity}',
                        },
                    },
                    'quantity': item.quantity,
                })

            # Создаем Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',

                # КРИТИЧЕСКИ ВАЖНО: metadata для восстановления заказа
                # В случае сбоя мы сможем восстановить заказ по этим данным
                metadata={
                    'order_id': str(order.order_id),
                    'chat_id': str(order.chat_id),
                    'phone': order.phone,
                    'address': order.address,
                    'total_amount': str(order.total_amount),
                    'created_at': order.created_at.isoformat(),
                },

                # Client reference для дополнительной идентификации
                client_reference_id=f"order_{order.order_id}",

                # URLs для редиректа
                success_url=self.success_url,
                cancel_url=self.cancel_url,

                # Время жизни сессии: 4 часа
                # (пользователь может отвлечься, вернуться позже)
                expires_at=int(order.created_at.timestamp() + 14400),

                # Payment Intent настройки
                payment_intent_data={
                    'description': f'Order #{order.order_id} - {order.phone}',
                    'metadata': {
                        'order_id': str(order.order_id),
                        'chat_id': str(order.chat_id),
                    },
                    # Можно добавить statement_descriptor для выписки
                    # 'statement_descriptor': 'YOUR_SHOP',
                },

                # Дополнительные опции для лучшего UX
                billing_address_collection='auto',
                phone_number_collection={'enabled': True},

                # Автоматические налоги (если настроено в Stripe)
                # automatic_tax={'enabled': True},

                # Поддержка промокодов (если нужно)
                # allow_promotion_codes=True,
            )

            logger.info(
                f"✅ Stripe Checkout Session created: {session.id} "
                f"for order #{order.order_id}"
            )

            return {
                'payment_url': session.url,
                'payment_id': session.id,
                'status': session.status,
                'metadata': {
                    'session_id': session.id,
                    'payment_intent': session.payment_intent,
                    'expires_at': session.expires_at,
                },
            }

        except stripe.error.CardError as e:
            # Ошибка карты (недостаточно средств и т.д.)
            logger.error(f"❌ Stripe CardError: {e}")
            raise PaymentProviderError(f"Card error: {e.user_message}") from e

        except stripe.error.InvalidRequestError as e:
            # Неверные параметры запроса
            logger.error(f"❌ Stripe InvalidRequestError: {e}")
            raise PaymentProviderError(f"Invalid request: {str(e)}") from e

        except stripe.error.AuthenticationError as e:
            # Проблемы с API ключом
            logger.error(f"❌ Stripe AuthenticationError: {e}")
            raise PaymentProviderError("Payment system authentication error") from e

        except stripe.error.APIConnectionError as e:
            # Сетевые проблемы
            logger.error(f"❌ Stripe APIConnectionError: {e}")
            raise PaymentProviderError("Payment system connection error") from e

        except stripe.error.StripeError as e:
            # Любая другая ошибка Stripe
            logger.error(f"❌ Stripe error: {e}")
            raise PaymentProviderError(f"Stripe error: {str(e)}") from e

        except Exception as e:
            # Неожиданная ошибка
            logger.error(f"❌ Unexpected error creating payment: {e}", exc_info=True)
            raise PaymentProviderError(f"Payment creation failed: {str(e)}") from e

    async def verify_payment(self, payment_id: str) -> bool:
        """
        Проверяет статус Checkout Session.

        Это основной метод для polling - вызывается регулярно
        фоновым worker'ом.

        Args:
            payment_id: ID Stripe Checkout Session

        Returns:
            bool: True если оплачен
        """
        try:
            session = stripe.checkout.Session.retrieve(
                payment_id,
                expand=['payment_intent']  # Получаем детали payment intent
            )

            is_paid = session.payment_status == 'paid'

            if is_paid:
                logger.info(f"✅ Payment verified: {payment_id}")

            return is_paid

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error verifying payment {payment_id}: {e}")
            return False

    async def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает полную информацию о Checkout Session.

        Используется при обработке успешного платежа.

        Args:
            payment_id: ID Checkout Session

        Returns:
            Optional[Dict]: Детали сессии или None
        """
        try:
            session = stripe.checkout.Session.retrieve(
                payment_id,
                expand=['payment_intent', 'customer']
            )

            return {
                'session_id': session.id,
                'payment_status': session.payment_status,
                'payment_intent_id': (
                    session.payment_intent.id
                    if session.payment_intent else None
                ),
                'amount_total': session.amount_total,
                'amount_received': (
                    session.payment_intent.amount_received
                    if session.payment_intent else None
                ),
                'currency': session.currency,
                'customer_email': (
                    session.customer_details.email
                    if session.customer_details else None
                ),
                'customer_phone': (
                    session.customer_details.phone
                    if session.customer_details else None
                ),
                'metadata': session.metadata,
                'created': session.created,
                'expires_at': session.expires_at,
            }

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error retrieving session {payment_id}: {e}")
            return None

    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Отменяет незавершенный платеж.

        Note: Stripe Checkout Sessions нельзя отменить явно,
        но можно отменить Payment Intent если он еще не подтвержден.

        Args:
            payment_id: ID Checkout Session

        Returns:
            bool: True если отмена успешна
        """
        try:
            session = stripe.checkout.Session.retrieve(payment_id)

            if session.payment_intent:
                payment_intent = stripe.PaymentIntent.retrieve(
                    session.payment_intent
                )

                # Отменить можно только если платеж еще не подтвержден
                if payment_intent.status in [
                    'requires_payment_method',
                    'requires_confirmation',
                    'requires_action'
                ]:
                    stripe.PaymentIntent.cancel(session.payment_intent)
                    logger.info(f"✅ Cancelled Payment Intent: {session.payment_intent}")
                    return True
                else:
                    logger.warning(
                        f"⚠️ Cannot cancel Payment Intent in status: "
                        f"{payment_intent.status}"
                    )
                    return False

            return False

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error cancelling payment {payment_id}: {e}")
            return False

    @property
    def provider_name(self) -> str:
        """Название провайдера."""
        return "Stripe"

    async def refund_payment(
            self,
            payment_intent_id: str,
            amount: Optional[int] = None
    ) -> bool:
        """
        Возврат средств (дополнительный метод).

        Args:
            payment_intent_id: ID Payment Intent
            amount: Сумма возврата в центах (None = полный возврат)

        Returns:
            bool: True если возврат успешен
        """
        try:
            refund_params = {'payment_intent': payment_intent_id}
            if amount:
                refund_params['amount'] = amount

            refund = stripe.Refund.create(**refund_params)

            logger.info(
                f"✅ Refund created: {refund.id} "
                f"for Payment Intent: {payment_intent_id}"
            )
            return refund.status in ['succeeded', 'pending']

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error creating refund: {e}")
            return False