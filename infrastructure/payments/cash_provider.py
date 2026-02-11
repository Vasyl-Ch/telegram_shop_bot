"""
Cash on Delivery (COD) платежный провайдер.

Особенности:
- Не создает реальных платежей
- "Null object" pattern
- Соответствует интерфейсу PaymentProvider
- Платеж подтверждается менеджером вручную
"""

from typing import Dict, Any, Optional
import logging

from infrastructure.payments.payment_provider import PaymentProvider
from domain.entities.order import Order

logger = logging.getLogger(__name__)


class CashProvider(PaymentProvider):
    """
    Cash on Delivery provider.

    Особенности:
    - Не создает внешних платежей
    - Платеж считается "pending" до подтверждения менеджером
    - Не требует webhook или polling
    - Подтверждение через Telegram кнопки менеджера
    """

    async def create_payment(self, order: Order) -> Dict[str, Any]:
        """
        "Создает" COD платеж (фактически просто логирует).

        Args:
            order: Заказ

        Returns:
            Dict с минимальными данными (нет payment_url)
        """
        logger.info(
            f"💵 COD payment initiated for order #{order.order_id}, "
            f"amount: {order.total_amount}₽"
        )

        # Генерируем уникальный ID для "платежа"
        payment_id = f"cash_{order.order_id}_{int(order.created_at.timestamp())}"

        return {
            'payment_url': None,  # Нет URL — оплата при получении
            'payment_id': payment_id,
            'status': 'pending_confirmation',  # Ожидает подтверждения менеджера
            'metadata': {
                'method': 'cash_on_delivery',
                'requires_manager_confirmation': True,
                'amount': float(order.total_amount),
            },
        }

    async def verify_payment(self, payment_id: str) -> bool:
        """
        COD платежи не могут быть верифицированы автоматически.

        Требуется ручное подтверждение менеджера при доставке.

        Args:
            payment_id: ID "платежа"

        Returns:
            bool: Всегда False (нужно ручное подтверждение)
        """
        logger.debug(f"💵 COD payment verification requested for {payment_id}")
        return False

    async def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает минимальную информацию о COD платеже.

        Args:
            payment_id: ID "платежа"

        Returns:
            Optional[Dict]: Детали
        """
        # Парсим payment_id для получения информации
        # Формат: cash_<order_id>_<timestamp>
        try:
            parts = payment_id.split('_')
            if len(parts) >= 3 and parts[0] == 'cash':
                return {
                    'payment_id': payment_id,
                    'method': 'cash_on_delivery',
                    'status': 'pending_confirmation',
                    'order_id': int(parts[1]),
                    'created': int(parts[2]),
                }
        except Exception as e:
            logger.error(f"Error parsing COD payment_id {payment_id}: {e}")

        return None

    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Отмена COD — просто логирование.

        Args:
            payment_id: ID "платежа"

        Returns:
            bool: Всегда True (нет внешнего платежа для отмены)
        """
        logger.info(f"❌ COD payment cancelled: {payment_id}")
        return True

    @property
    def provider_name(self) -> str:
        """Название провайдера."""
        return "Cash on Delivery"