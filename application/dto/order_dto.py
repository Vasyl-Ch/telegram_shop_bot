"""
Data Transfer Objects for orders.

Adapted to the real architecture of the project:
- OrderCreateDTO: checkout_handler → OrderService
- PaymentMethodDTO: checkout_handler → OrderService
- OrderResponseDTO: OrderService → checkout_handler/seller_handler
- OrderSummaryDTO: OrderService → handlers
- PaymentResultDTO: PaymentService → checkout_handler
- CheckoutStateDTO: Replace raw dict _checkout_state
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
import re

from domain.entities.order import Order, OrderItem
from domain.enums.order_status import OrderStatus
from domain.enums.payment_method import PaymentMethod

# ─────────────────────────────────────────────
# INPUT DTOs (Presentation → Application)
# ─────────────────────────────────────────────


@dataclass
class OrderCreateDTO:
    """
    Checkout form data.

    Replaces three separate arguments in the OrderService:
        Before: create_order_from_cart(cart, phone, address)
        After: create_order_from_cart(cart, dto)

    Crafted in checkout_handler after harvesting
    phone number and address from the user.
    """

    chat_id: int
    """ID пользователя в Telegram."""

    phone: str
    """Номер телефона покупателя."""

    address: str
    """Адрес доставки."""

    def __post_init__(self):
        self.phone = self.phone.strip()
        self.address = self.address.strip()

        phone_pattern = (
            r"^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}$"
        )
        if not re.match(phone_pattern, self.phone):
            raise ValueError(
                f"Некорректный формат телефона: '{self.phone}'. "
                "Пример: +380 99 123 45 67"
            )

        if not self.address or len(self.address) < 10:
            raise ValueError(f"Адрес слишком короткий: '{self.address}'")

        if not self.chat_id or self.chat_id <= 0:
            raise ValueError(f"Некорректный chat_id: {self.chat_id}")


@dataclass
class PaymentMethodDTO:
    """
    Choosing a payment method.

    Created in checkout_handler when the user
    clicks the payment selection button.
    """

    order_id: int
    """ID заказа."""

    payment_method: PaymentMethod
    """Выбранный способ оплаты."""

    @classmethod
    def from_callback(
        cls,
        order_id: int,
        method_value: str,
    ) -> "PaymentMethodDTO":
        """
        Creates a DTO from callback_data Telegram buttons.

        Args:
            order_id: Order ID
            method_value: String value from callback
                          (e.g. "stripe" or "cash")

        Returns:
            PaymentMethodDTO

        Raises:
            ValueError: If method_value unknown
        """
        try:
            method = PaymentMethod(method_value)
        except ValueError:
            raise ValueError(f"Неизвестный способ оплаты: '{method_value}'")

        return cls(order_id=order_id, payment_method=method)


@dataclass
class CheckoutStateDTO:
    """
    The status of the checkout process.

    Replaces the raw dict _checkout_state in checkout_handler:
        was: _checkout_state[chat_id] = {"phone": ..., "address": ...}
        after: _checkout_state[chat_id] = CheckoutStateDTO(...)

    Stores intermediate data between form steps
    (the phone is collected at step 1, the address at step 2).
    """

    chat_id: int
    """ID пользователя."""

    phone: str = ""
    """Телефон (заполняется на шаге 1)."""

    address: str = ""
    """Адрес (заполняется на шаге 2)."""

    started_at: datetime = field(default_factory=datetime.now)
    """Время начала оформления (для TTL/истечения)."""

    def is_phone_collected(self) -> bool:
        """Checks if the phone is entered."""
        return bool(self.phone and len(self.phone) >= 10)

    def is_complete(self) -> bool:
        """Checks if all the data has been collected to create the order."""
        return self.is_phone_collected() and len(self.address) >= 10

    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """
        Checks if the checkout session has expired.

        Args:
            ttl_minutes: Lifetime in minutes

        Returns:
            bool: True if the session is out of date
        """
        age = (datetime.now() - self.started_at).total_seconds() / 60
        return age > ttl_minutes

    def to_order_create_dto(self) -> OrderCreateDTO:
        """
        Converts to OrderCreateDTO when the data is collected.

        Returns:
            OrderCreateDTO: Ready DTO to be passed to OrderService

        Raises:
            ValueError: If the data has not yet been collected
        """
        if not self.is_complete():
            raise ValueError("Данные оформления ещё не собраны полностью")

        return OrderCreateDTO(
            chat_id=self.chat_id,
            phone=self.phone,
            address=self.address,
        )


# ─────────────────────────────────────────────
# OUTPUT DTOs (Application → Presentation)
# ─────────────────────────────────────────────


@dataclass
class OrderItemDTO:
    """
    Order item to be transferred to the Presentation layer.

    A planar structure with no methods—only data.
    """

    product_id: int
    name: str
    quantity: int
    price: Decimal
    total: Decimal

    @classmethod
    def from_order_item(cls, item: OrderItem) -> "OrderItemDTO":
        """
        Creates a DTO from the domain's OrderItem.

        Args:
            item: Domain Object

        Returns:
            OrderItemDTO
        """
        return cls(
            product_id=item.product_id,
            name=item.name,
            quantity=item.quantity,
            price=item.price,
            total=item.total,
        )

    def to_dict(self) -> dict:
        """Serialization to a dictionary."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "quantity": self.quantity,
            "price": float(self.price),
            "total": float(self.total),
        }


@dataclass
class OrderResponseDTO:
    """
    Full order data for the Presentation layer.

    Returned from OrderService instead of domain Order.
    Handlers work ONLY with this DTO – do not import the Order.

    Contains precomputed display fields to
    formatters did not depend on domain enums.
    """

    order_id: int
    chat_id: int
    items: List[OrderItemDTO]
    phone: str
    address: str
    status: OrderStatus
    total_amount: Decimal
    items_count: int

    payment_method: Optional[PaymentMethod] = None
    payment_url: Optional[str] = None
    stripe_session_id: Optional[str] = None
    seller_message_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    status_display: str = field(init=False)
    payment_method_display: str = field(init=False)

    def __post_init__(self):
        """Populates display fields from enum values."""
        self.status_display = self.status.display_name
        self.payment_method_display = (
            self.payment_method.display_name if self.payment_method else "Не выбран"
        )

    @classmethod
    def from_order(
        cls,
        order: Order,
        payment_url: Optional[str] = None,
    ) -> "OrderResponseDTO":
        """
        The main factory method is Order → DTO.

        Used in OrderService before return
        data in the Presentation layer.

        Args:
            order: Domain object of the order
            payment_url: Payment Stripe URL (if any)

        Returns:
            OrderResponseDTO
        """
        return cls(
            order_id=order.order_id,
            chat_id=order.chat_id,
            items=[OrderItemDTO.from_order_item(item) for item in order.items],
            phone=order.phone,
            address=order.address,
            status=order.status,
            total_amount=order.total_amount,
            items_count=order.items_count,
            payment_method=order.payment_method,
            payment_url=payment_url,
            stripe_session_id=order.stripe_session_id,
            seller_message_id=order.seller_message_id,
            created_at=order.created_at,
        )

    def to_dict(self) -> dict:
        """Serialization (for logs and debugging)."""
        return {
            "order_id": self.order_id,
            "chat_id": self.chat_id,
            "items": [i.to_dict() for i in self.items],
            "phone": self.phone,
            "address": self.address,
            "status": self.status.value,
            "status_display": self.status_display,
            "total_amount": float(self.total_amount),
            "payment_method": (
                self.payment_method.value if self.payment_method else None
            ),
            "payment_url": self.payment_url,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class OrderSummaryDTO:
    """
    A quick summary of the order for the lists.

    Used in:
    - "📦 My Orders" (customer story)
    - "📋 Active orders" (seller panel)

    Easier than OrderResponseDTO — without a full list of items.
    """

    order_id: int
    status: OrderStatus
    total_amount: Decimal
    items_count: int
    payment_method: Optional[PaymentMethod]
    created_at: datetime

    status_display: str = field(init=False)
    payment_method_display: str = field(init=False)

    def __post_init__(self):
        self.status_display = self.status.display_name
        self.payment_method_display = (
            self.payment_method.display_name if self.payment_method else "Не выбран"
        )

    @classmethod
    def from_order(cls, order: Order) -> "OrderSummaryDTO":
        """
        Creates a summary from the domain Order.

        Args:
            order: Domain Object

        Returns:
            OrderSummaryDTO
        """
        return cls(
            order_id=order.order_id,
            status=order.status,
            total_amount=order.total_amount,
            items_count=order.items_count,
            payment_method=order.payment_method,
            created_at=order.created_at,
        )


@dataclass
class PaymentResultDTO:
    """
    The result of verification/processing of the payment.

    Returning from PaymentService.check_stripe_payment()
    in checkout_handler.

    Isolates handler from Stripe API details —
    Handler only sees: paid/no + message.
    """

    order_id: int
    """ID заказа."""

    is_paid: bool
    """Успешно ли оплачен."""

    new_status: OrderStatus
    """Статус заказа после проверки."""

    message_for_user: str
    """Готовое сообщение для отправки пользователю."""

    updated_order_dto: Optional[OrderResponseDTO] = None
    """Обновлённый DTO заказа (если статус изменился)."""

    payment_intent_id: Optional[str] = None
    """ID Stripe Payment Intent."""
