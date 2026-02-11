"""
Order entity (заказ).

Применение DDD и SOLID:
- Order - это Aggregate Root (управляет жизненным циклом заказа)
- Инкапсулирует бизнес-логику переходов между статусами
- Single Responsibility: только логика заказа
- Immutable где возможно, mutable где необходимо (статус, metadata)
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
    Товар в заказе (Value Object).

    Snapshot товара на момент оформления заказа.
    """

    product_id: int
    """ID товара."""

    name: str
    """Название товара."""

    quantity: int
    """Количество."""

    price: Decimal
    """Цена за единицу на момент заказа."""

    @property
    def total(self) -> Decimal:
        """Стоимость позиции."""
        return self.price * self.quantity

    def to_dict(self) -> dict:
        """Преобразование в словарь."""
        return {
            'product_id': self.product_id,
            'name': self.name,
            'quantity': self.quantity,
            'price': float(self.price),
            'total': float(self.total),
        }


@dataclass
class Order:
    """
    Агрегат заказа (Aggregate Root).

    Инвариант: заказ всегда в валидном состоянии.
    Управляет переходами между статусами согласно бизнес-правилам.
    """

    order_id: int
    """Уникальный ID заказа."""

    chat_id: int
    """ID пользователя в Telegram."""

    items: List[OrderItem]
    """Товары в заказе."""

    phone: str
    """Телефон покупателя."""

    address: str
    """Адрес доставки."""

    status: OrderStatus
    """Текущий статус заказа."""

    payment_method: Optional[PaymentMethod] = None
    """Способ оплаты (выбирается после создания заказа)."""

    # Stripe-специфичные поля
    stripe_session_id: Optional[str] = None
    """ID Stripe Checkout Session."""

    stripe_payment_intent_id: Optional[str] = None
    """ID Stripe Payment Intent."""

    # Метаданные
    created_at: datetime = field(default_factory=datetime.now)
    """Время создания заказа."""

    updated_at: datetime = field(default_factory=datetime.now)
    """Время последнего обновления."""

    # UI sync (для обновления сообщений в Telegram)
    seller_message_id: Optional[int] = None
    """ID сообщения в чате менеджера."""

    customer_message_id: Optional[int] = None
    """ID сообщения в чате покупателя."""

    # Заметки менеджера
    notes: Optional[str] = None
    """Дополнительные заметки."""

    def __post_init__(self):
        """Валидация после инициализации."""
        if not self.items:
            raise ValueError("Order must contain at least one item")

        if not self.phone or len(self.phone) < 10:
            raise ValueError("Invalid phone number")

        if not self.address or len(self.address) < 10:
            raise ValueError("Invalid address")

    @property
    def total_amount(self) -> Decimal:
        """
        Общая сумма заказа.

        Returns:
            Decimal: Сумма всех позиций
        """
        return sum(item.total for item in self.items)

    @property
    def total_amount_cents(self) -> int:
        """
        Сумма в копейках/центах (для Stripe API).

        Returns:
            int: Сумма в минимальных единицах валюты
        """
        return int(self.total_amount * 100)

    @property
    def items_count(self) -> int:
        """
        Общее количество товаров.

        Returns:
            int: Количество единиц
        """
        return sum(item.quantity for item in self.items)

    def update_status(self, new_status: OrderStatus, notes: Optional[str] = None) -> None:
        """
        Обновляет статус заказа с валидацией переходов.

        Применение State Machine pattern:
        - Проверяет допустимость перехода
        - Логирует изменения
        - Обновляет timestamp

        Args:
            new_status: Новый статус
            notes: Опциональные заметки о причине изменения

        Raises:
            ValueError: Если переход недопустим (в strict режиме)
        """
        if new_status == self.status:
            # Переход в тот же статус - игнорируем
            return

        # Проверяем допустимость перехода
        if not self.status.can_transition_to(new_status):
            logger.warning(
                f"⚠️ Invalid status transition for order #{self.order_id}: "
                f"{self.status.value} → {new_status.value}"
            )
            # В production можно сделать строже (raise ValueError)
            # Пока только логируем warning

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
        Устанавливает способ оплаты.

        Args:
            method: Способ оплаты
        """
        self.payment_method = method
        self.updated_at = datetime.now()

        # Автоматически обновляем статус в зависимости от метода
        if method == PaymentMethod.STRIPE:
            self.update_status(OrderStatus.PENDING_PAYMENT)
        elif method == PaymentMethod.CASH:
            self.update_status(OrderStatus.CONFIRMED)

        logger.info(
            f"💳 Order #{self.order_id} payment method set: {method.value}"
        )

    def set_stripe_session(self, session_id: str) -> None:
        """
        Сохраняет ID Stripe Checkout Session.

        Args:
            session_id: ID сессии
        """
        self.stripe_session_id = session_id
        self.updated_at = datetime.now()

    def set_stripe_payment_intent(self, payment_intent_id: str) -> None:
        """
        Сохраняет ID Stripe Payment Intent.

        Args:
            payment_intent_id: ID payment intent
        """
        self.stripe_payment_intent_id = payment_intent_id
        self.updated_at = datetime.now()

    def is_paid(self) -> bool:
        """
        Проверяет, оплачен ли заказ.

        Returns:
            bool: True если оплачен
        """
        return self.status.is_paid

    def is_final(self) -> bool:
        """
        Проверяет, в финальном ли статусе заказ.

        Returns:
            bool: True если заказ завершен
        """
        return self.status.is_final

    def requires_online_payment(self) -> bool:
        """
        Требуется ли онлайн-оплата.

        Returns:
            bool: True если нужен payment gateway
        """
        return (
                self.payment_method is not None and
                self.payment_method.requires_online_payment
        )

    def get_summary(self) -> str:
        """
        Краткая сводка заказа для отображения.

        Returns:
            str: Текстовое описание заказа
        """
        items_text = "\n".join(
            f"• {item.name} ×{item.quantity} — {item.total}₽"
            for item in self.items
        )

        payment_info = (
            self.payment_method.display_name
            if self.payment_method
            else "Не выбран"
        )

        return (
            f"📦 Заказ #{self.order_id}\n"
            f"Статус: {self.status.display_name}\n"
            f"Способ оплаты: {payment_info}\n\n"
            f"Товары:\n{items_text}\n\n"
            f"💰 Итого: {self.total_amount}₽\n"
            f"📱 Телефон: {self.phone}\n"
            f"🏠 Адрес: {self.address}\n"
            f"📅 Создан: {self.created_at.strftime('%d.%m.%Y %H:%M')}"
        )

    def to_dict(self) -> dict:
        """
        Преобразует заказ в словарь (для сериализации).

        Returns:
            dict: Данные заказа
        """
        return {
            'order_id': self.order_id,
            'chat_id': self.chat_id,
            'items': [item.to_dict() for item in self.items],
            'phone': self.phone,
            'address': self.address,
            'status': self.status.value,
            'payment_method': self.payment_method.value if self.payment_method else None,
            'stripe_session_id': self.stripe_session_id,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'total_amount': float(self.total_amount),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'notes': self.notes,
        }