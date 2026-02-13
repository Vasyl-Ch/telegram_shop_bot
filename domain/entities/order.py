"""
Order entity.

Applications of DDD and SOLID:
- Order is the Aggregate Root (manages the order lifecycle)
- Encapsulates the business logic of transitions between statuses
- Single Responsibility: Order logic only
- Immutable where possible, mutable where necessary (status, metadata)
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import logging

from domain.enums.order_status import OrderStatus
from domain.enums.payment_method import PaymentMethod

logger = logging.getLogger(__name__)


@dataclass
class OrderItem:
    """
    The product in the order (Value Object).

    Snapshot of the product at the time of checkout.
    """

    product_id: int
    name: str
    quantity: int
    price: Decimal

    @property
    def total(self) -> Decimal:
        """Position value."""
        return self.price * self.quantity

    def to_dict(self) -> dict:
        """Conversion to a dictionary."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "quantity": self.quantity,
            "price": float(self.price),
            "total": float(self.total),
        }


@dataclass
class Order:
    """
    Aggregate Root.

    Invariant: the order is always in a valid state.
    Manages transitions between statuses according to business rules.
    """

    order_id: int
    chat_id: int
    items: List[OrderItem]
    phone: str
    address: str
    status: OrderStatus
    payment_method: Optional[PaymentMethod] = None

    stripe_session_id: Optional[str] = None
    """ID Stripe Checkout Session."""

    stripe_payment_intent_id: Optional[str] = None
    """ID Stripe Payment Intent."""

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    seller_message_id: Optional[int] = None
    customer_message_id: Optional[int] = None

    notes: Optional[str] = None

    def __post_init__(self):
        """Validation after initialization."""
        if not self.items:
            raise ValueError("Order must contain at least one item")

        if not self.phone or len(self.phone) < 10:
            raise ValueError("Invalid phone number")

        if not self.address or len(self.address) < 10:
            raise ValueError("Invalid address")

    @property
    def total_amount(self) -> Decimal:
        """
        The total amount of the order.

        Returns:
            Decimal: Sum of all positions
        """
        return sum(item.total for item in self.items)

    @property
    def total_amount_cents(self) -> int:
        """
        Amount in kopecks/cents (for Stripe API).

        Returns:
            int: Amount in minimum currency units
        """
        return int(self.total_amount * 100)

    @property
    def items_count(self) -> int:
        """
        Total number of products.

        Returns:
            int: Number of units
        """
        return sum(item.quantity for item in self.items)

    def update_status(
        self, new_status: OrderStatus, notes: Optional[str] = None
    ) -> None:
        """
        Updates the status of the order with the validation of transitions.

        Application of State Machine pattern:
        - Checks the admissibility of the transition
        - Logs changes
        - Updates the timestamp

        Args:
            new_status: New Status
            notes: Optional notes about the reason for the change

        Raises:
            ValueError: If the transition is invalid (in strict mode)
        """
        if new_status == self.status:
            return

        if not self.status.can_transition_to(new_status):
            logger.warning(
                f"⚠️ Invalid status transition for order #{self.order_id}: "
                f"{self.status.value} → {new_status.value}"
            )

        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now()

        if notes:
            self.notes = notes

        logger.info(
            f"✅ Order #{self.order_id} status changed: "
            f"{old_status.value} → {new_status.value}"
        )

    def set_payment_method(self, method: PaymentMethod) -> None:
        """
        Sets the payment method.

        Args:
            method: Payment method
        """
        self.payment_method = method
        self.updated_at = datetime.now()

        if method == PaymentMethod.STRIPE:
            self.update_status(OrderStatus.PENDING_PAYMENT)
        elif method == PaymentMethod.CASH:
            self.update_status(OrderStatus.PENDING_CONFIRMATION)

        logger.info(f"💳 Order #{self.order_id} payment method set: {method.value}")

    def set_stripe_session(self, session_id: str) -> None:
        """
        Saves the ID of the Stripe Checkout Session.

        Args:
            session_id: Session ID
        """
        self.stripe_session_id = session_id
        self.updated_at = datetime.now()

    def set_stripe_payment_intent(self, payment_intent_id: str) -> None:
        """
        Saves the ID of the Stripe Payment Intent.

        Args:
            payment_intent_id: ID Payment Intent
        """
        self.stripe_payment_intent_id = payment_intent_id
        self.updated_at = datetime.now()

    def is_paid(self) -> bool:
        """
        Checks whether the order has been paid for.

        Returns:
            bool: True if paid
        """
        return self.status.is_paid

    def is_stripe_paid(self) -> bool:
        """
        Checks that the Stripe order has been paid.

        Returns:
            bool: True if Stripe order is successfully paid
        """
        return self.payment_method == PaymentMethod.STRIPE and self.status in [
            OrderStatus.PAID,
            OrderStatus.CONFIRMED,
            OrderStatus.DELIVERED,
        ]

    def is_final(self) -> bool:
        """
        Checks if the order is in the final status.

        Returns:
            bool: True if the order is completed
        """
        return self.status.is_final

    def requires_online_payment(self) -> bool:
        """
        Is online payment required?

        Returns:
            bool: True if payment gateway is needed
        """
        return (
            self.payment_method is not None
            and self.payment_method.requires_online_payment
        )

    def get_summary(self) -> str:
        """
        A brief summary of the order to display.

        Returns:
            str: Text description of the order
        """
        items_text = "\n".join(
            f"• {item.name} ×{item.quantity} — {item.total}₴" for item in self.items
        )

        payment_info = (
            self.payment_method.display_name if self.payment_method else "Не выбран"
        )

        return (
            f"📦 Заказ #{self.order_id}\n"
            f"Статус: {self.status.display_name}\n"
            f"Способ оплаты: {payment_info}\n\n"
            f"Товары:\n{items_text}\n\n"
            f"💰 Итого: {self.total_amount}₴\n"
            f"📱 Телефон: {self.phone}\n"
            f"🏠 Адрес: {self.address}\n"
            f"📅 Создан: {self.created_at.strftime('%d.%m.%Y %H:%M')}"
        )

    def to_dict(self) -> dict:
        """
        Converts the order to a dictionary (for serialization).

        Returns:
            dict: Order Data
        """
        return {
            "order_id": self.order_id,
            "chat_id": self.chat_id,
            "items": [item.to_dict() for item in self.items],
            "phone": self.phone,
            "address": self.address,
            "status": self.status.value,
            "payment_method": (
                self.payment_method.value if self.payment_method else None
            ),
            "stripe_session_id": self.stripe_session_id,
            "stripe_payment_intent_id": self.stripe_payment_intent_id,
            "total_amount": float(self.total_amount),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "notes": self.notes,
        }
