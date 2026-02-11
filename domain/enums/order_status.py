"""
Enum for order statuses.

Statuses are organized like a State Machine:
- Each status has certain valid transitions
- Disabled crossings are logged as a warning
"""

from enum import Enum
from typing import List


class OrderStatus(str, Enum):
    """
    Статусы жизненного цикла заказа.

    Flow для онлайн-оплаты (Stripe):
    PENDING_PAYMENT_METHOD → PENDING_PAYMENT → PAID → CONFIRMED → DELIVERED

    Flow для наличных:
    PENDING_PAYMENT_METHOD → PENDING_CONFIRMATION → CONFIRMED → DELIVERED

    Отмена возможна на любом этапе до DELIVERED.

    """

    PENDING_PAYMENT_METHOD = "pending_payment_method"
    """Ожидает выбора способа оплаты."""

    PENDING_PAYMENT = "pending_payment"
    """Ожидает онлайн-оплаты (создана Stripe session)."""

    PENDING_CONFIRMATION = "pending_confirmation"
    """Ожидает подтверждения менеджером (наличные)."""

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
        Human-readable name for UI.

        Returns:
            str: Title with emoji
        """
        names = {
            self.PENDING_PAYMENT_METHOD: "⏳ Выбор способа оплаты",
            self.PENDING_PAYMENT: "⏳ Ожидает оплаты",
            self.PENDING_CONFIRMATION: "⏳ Ожидает подтверждения",
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
        Checking the final status.

        Returns:
            bool: True if the order is in the final state
        """
        return self in [
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED,
        ]

    @property
    def is_paid(self) -> bool:
        """
        Checking the payment for the order.

        Returns:
            bool: True if the order is paid
        """
        return self in [
            OrderStatus.PAID,
            OrderStatus.PENDING_CONFIRMATION,
            OrderStatus.CONFIRMED,
            OrderStatus.DELIVERED,
        ]

    @property
    def requires_manager_action(self) -> bool:
        """
        Whether a manager's action is required.

        Returns:
            bool: True if need manager confirmation
        """
        return self in [
            OrderStatus.PENDING_CONFIRMATION,
            OrderStatus.PAID,
            OrderStatus.CONFIRMED,
        ]

    def get_allowed_transitions(self) -> List["OrderStatus"]:
        """
        Returns a list of valid transitions from the current status.

        Returns:
            List[OrderStatus]: The following statuses are valid
        """
        transitions = {
            OrderStatus.PENDING_PAYMENT_METHOD: [
                OrderStatus.PENDING_PAYMENT,
                OrderStatus.PENDING_CONFIRMATION,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PENDING_PAYMENT: [
                OrderStatus.PAYMENT_PROCESSING,
                OrderStatus.PAID,
                OrderStatus.FAILED,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PENDING_CONFIRMATION: [
                OrderStatus.CONFIRMED,
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
            OrderStatus.DELIVERED: [],
            OrderStatus.CANCELLED: [],
            OrderStatus.FAILED: [
                OrderStatus.PENDING_PAYMENT_METHOD,
            ],
        }
        return transitions.get(self, [])

    def can_transition_to(self, new_status: "OrderStatus") -> bool:
        """
        Checks the admissibility of the transition to the new status.

        Args:
            new_status: Target Status

        Returns:
            bool: True if the transition is valid
        """
        if new_status == self:
            return True
        return new_status in self.get_allowed_transitions()
