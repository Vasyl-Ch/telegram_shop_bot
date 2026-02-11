"""
Data Transfer Objects для заказов.

Адаптированы под реальную архитектуру проекта:
- OrderCreateDTO: checkout_handler → OrderService
- PaymentMethodDTO: checkout_handler → OrderService
- OrderResponseDTO: OrderService → checkout_handler/seller_handler
- OrderSummaryDTO: OrderService → handlers (список заказов)
- PaymentResultDTO: PaymentService → checkout_handler
- CheckoutStateDTO: замена сырого dict _checkout_state
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
    Данные формы оформления заказа.

    Заменяет три отдельных аргумента в OrderService:
        было:  create_order_from_cart(cart, phone, address)
        стало: create_order_from_cart(cart, dto)

    Создаётся в checkout_handler после сбора
    телефона и адреса от пользователя.
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

        phone_pattern = r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}$'
        if not re.match(phone_pattern, self.phone):
            raise ValueError(
                f"Некорректный формат телефона: '{self.phone}'. "
                "Пример: +7 999 123-45-67"
            )

        if not self.address or len(self.address) < 10:
            raise ValueError(f"Адрес слишком короткий: '{self.address}'")

        if not self.chat_id or self.chat_id <= 0:
            raise ValueError(f"Некорректный chat_id: {self.chat_id}")


@dataclass
class PaymentMethodDTO:
    """
    Выбор способа оплаты.

    Создаётся в checkout_handler когда пользователь
    нажимает кнопку выбора оплаты.
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
        Создаёт DTO из callback_data Telegram кнопки.

        Args:
            order_id: ID заказа
            method_value: Строковое значение из callback
                          (например "stripe" или "cash")

        Returns:
            PaymentMethodDTO

        Raises:
            ValueError: если method_value неизвестен
        """
        try:
            method = PaymentMethod(method_value)
        except ValueError:
            raise ValueError(
                f"Неизвестный способ оплаты: '{method_value}'"
            )

        return cls(order_id=order_id, payment_method=method)


@dataclass
class CheckoutStateDTO:
    """
    Состояние процесса оформления заказа.

    Заменяет сырой dict _checkout_state в checkout_handler:
        было:  _checkout_state[chat_id] = {"phone": ..., "address": ...}
        стало: _checkout_state[chat_id] = CheckoutStateDTO(...)

    Хранит промежуточные данные между шагами формы
    (телефон собирается на шаге 1, адрес на шаге 2).
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
        """Проверяет, введён ли телефон."""
        return bool(self.phone and len(self.phone) >= 10)

    def is_complete(self) -> bool:
        """Проверяет, собраны ли все данные для создания заказа."""
        return self.is_phone_collected() and len(self.address) >= 10

    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """
        Проверяет, не истекло ли время сессии оформления.

        Args:
            ttl_minutes: Время жизни в минутах

        Returns:
            bool: True если сессия устарела
        """
        age = (datetime.now() - self.started_at).total_seconds() / 60
        return age > ttl_minutes

    def to_order_create_dto(self) -> OrderCreateDTO:
        """
        Конвертирует в OrderCreateDTO когда данные собраны.

        Returns:
            OrderCreateDTO: Готовый DTO для передачи в OrderService

        Raises:
            ValueError: Если данные ещё не собраны
        """
        if not self.is_complete():
            raise ValueError(
                "Данные оформления ещё не собраны полностью"
            )

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
    Позиция заказа для передачи в Presentation layer.

    Плоская структура без методов — только данные.
    """

    product_id: int
    name: str
    quantity: int
    price: Decimal
    total: Decimal

    @classmethod
    def from_order_item(cls, item: OrderItem) -> "OrderItemDTO":
        """
        Создаёт DTO из доменного OrderItem.

        Args:
            item: Доменный объект

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
        """Сериализация в словарь."""
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
    Полные данные заказа для Presentation layer.

    Возвращается из OrderService вместо доменного Order.
    Handlers работают ТОЛЬКО с этим DTO — не импортируют Order.

    Содержит предвычисленные display-поля чтобы
    formatters не зависели от доменных enums.
    """

    order_id: int
    chat_id: int
    items: List[OrderItemDTO]
    phone: str
    address: str
    status: OrderStatus
    total_amount: Decimal
    items_count: int

    # Опциональные поля
    payment_method: Optional[PaymentMethod] = None
    payment_url: Optional[str] = None
    stripe_session_id: Optional[str] = None
    seller_message_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    # Предвычисленные display-поля для Presentation layer
    # (заполняются автоматически в __post_init__)
    status_display: str = field(init=False)
    payment_method_display: str = field(init=False)

    def __post_init__(self):
        """Заполняет display-поля из enum значений."""
        self.status_display = self.status.display_name
        self.payment_method_display = (
            self.payment_method.display_name
            if self.payment_method
            else "Не выбран"
        )

    @classmethod
    def from_order(
        cls,
        order: Order,
        payment_url: Optional[str] = None,
    ) -> "OrderResponseDTO":
        """
        Основной фабричный метод: Order → DTO.

        Используется в OrderService перед возвратом
        данных в Presentation layer.

        Args:
            order: Доменный объект заказа
            payment_url: URL Stripe оплаты (если есть)

        Returns:
            OrderResponseDTO
        """
        return cls(
            order_id=order.order_id,
            chat_id=order.chat_id,
            items=[
                OrderItemDTO.from_order_item(item)
                for item in order.items
            ],
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
        """Сериализация (для логов и отладки)."""
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
                self.payment_method.value
                if self.payment_method
                else None
            ),
            "payment_url": self.payment_url,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class OrderSummaryDTO:
    """
    Краткая сводка заказа для списков.

    Используется в:
    - "📦 Мои заказы" (история покупателя)
    - "📋 Активные заказы" (панель продавца)

    Легче OrderResponseDTO — без полного списка items.
    """

    order_id: int
    status: OrderStatus
    total_amount: Decimal
    items_count: int
    payment_method: Optional[PaymentMethod]
    created_at: datetime

    # Display поля
    status_display: str = field(init=False)
    payment_method_display: str = field(init=False)

    def __post_init__(self):
        self.status_display = self.status.display_name
        self.payment_method_display = (
            self.payment_method.display_name
            if self.payment_method
            else "Не выбран"
        )

    @classmethod
    def from_order(cls, order: Order) -> "OrderSummaryDTO":
        """
        Создаёт краткую сводку из доменного Order.

        Args:
            order: Доменный объект

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
    Результат проверки/обработки платежа.

    Возвращается из PaymentService.check_stripe_payment()
    в checkout_handler.

    Изолирует handler от деталей Stripe API —
    handler видит только: оплачено/нет + сообщение.
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