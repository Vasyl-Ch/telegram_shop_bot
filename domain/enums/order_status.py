"""
Enum для статусов заказа.

Статусы организованы как конечный автомат (State Machine):
- Каждый статус имеет определенные допустимые переходы
- Инвалидные переходы логируются как warning
"""

from enum import Enum
from typing import List


class OrderStatus(str, Enum):
    """
    Статусы жизненного цикла заказа.

    Flow для онлайн-оплаты (Stripe):
    PENDING_PAYMENT_METHOD → PENDING_PAYMENT → PAID → CONFIRMED → DELIVERED

    Flow для наличных:
    PENDING_PAYMENT_METHOD → CONFIRMED → DELIVERED

    Отмена возможна на любом этапе до DELIVERED.
    """

    PENDING_PAYMENT_METHOD = "pending_payment_method"
    """Ожидает выбора способа оплаты."""

    PENDING_PAYMENT = "pending_payment"
    """Ожидает онлайн-оплаты (создана Stripe session)."""

    PAYMENT_PROCESSING = "payment_processing"
    """Платеж обрабатывается Stripe (редко используется)."""

    PAID = "paid"
    """Оплачен через Stripe, ожидает подтверждения менеджера."""

    CONFIRMED = "confirmed"
    """Подтвержден менеджером, готов к доставке."""

    DELIVERED = "delivered"
    """Доставлен покупателю (финальный статус)."""

    CANCELLED = "cancelled"
    """Отменен менеджером или пользователем."""

    FAILED = "failed"
    """Ошибка оплаты или истек срок."""

    def __str__(self) -> str:
        """String representation."""
        return self.value

    @property
    def display_name(self) -> str:
        """
        Человекочитаемое название для UI.

        Returns:
            str: Название с emoji
        """
        names = {
            self.PENDING_PAYMENT_METHOD: "⏳ Выбор способа оплаты",
            self.PENDING_PAYMENT: "⏳ Ожидает оплаты",
            self.PAYMENT_PROCESSING: "🔄 Обработка платежа",
            self.PAID: "✅ Оплачен",
            self.CONFIRMED: "✅ Подтвержден менеджером",
            self.DELIVERED: "🚚 Доставлен",
            self.CANCELLED: "❌ Отменен",
            self.FAILED: "⚠️ Ошибка оплаты",
        }
        return names.get(self, self.value)

    @property
    def is_final(self) -> bool:
        """
        Проверка финального статуса.

        Returns:
            bool: True если заказ в финальном состоянии
        """
        return self in [
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED,
        ]

    @property
    def is_paid(self) -> bool:
        """
        Проверка оплаты заказа.

        Returns:
            bool: True если заказ оплачен
        """
        return self in [
            OrderStatus.PAID,
            OrderStatus.CONFIRMED,
            OrderStatus.DELIVERED,
        ]

    @property
    def requires_manager_action(self) -> bool:
        """
        Требуется ли действие менеджера.

        Returns:
            bool: True если нужно подтверждение менеджера
        """
        return self in [
            OrderStatus.PAID,
            OrderStatus.CONFIRMED,
        ]

    def get_allowed_transitions(self) -> List['OrderStatus']:
        """
        Возвращает список допустимых переходов из текущего статуса.

        Returns:
            List[OrderStatus]: Допустимые следующие статусы
        """
        transitions = {
            OrderStatus.PENDING_PAYMENT_METHOD: [
                OrderStatus.PENDING_PAYMENT,  # Выбрал Stripe
                OrderStatus.CONFIRMED,  # Выбрал наличные
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PENDING_PAYMENT: [
                OrderStatus.PAYMENT_PROCESSING,
                OrderStatus.PAID,
                OrderStatus.FAILED,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PAYMENT_PROCESSING: [
                OrderStatus.PAID,
                OrderStatus.FAILED,
            ],
            OrderStatus.PAID: [
                OrderStatus.CONFIRMED,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.CONFIRMED: [
                OrderStatus.DELIVERED,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.DELIVERED: [],  # Финальный статус
            OrderStatus.CANCELLED: [],  # Финальный статус
            OrderStatus.FAILED: [
                OrderStatus.PENDING_PAYMENT_METHOD,  # Можно переоформить
            ],
        }
        return transitions.get(self, [])

    def can_transition_to(self, new_status: 'OrderStatus') -> bool:
        """
        Проверяет допустимость перехода в новый статус.

        Args:
            new_status: Целевой статус

        Returns:
            bool: True если переход допустим
        """
        if new_status == self:
            return True  # Можно "перейти" в тот же статус
        return new_status in self.get_allowed_transitions()
