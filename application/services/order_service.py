"""
Order Service - оркестрация бизнес-логики заказов.

Применение SOLID:
- Single Responsibility: только логика заказов
- Dependency Injection: все зависимости через конструктор
- Interface Segregation: использует только нужные методы репозиториев
"""

import logging
from typing import List, Optional
from decimal import Decimal

from domain.entities.order import Order, OrderItem
from domain.entities.cart import Cart
from domain.enums.order_status import OrderStatus
from domain.enums.payment_method import PaymentMethod
from infrastructure.repositories.order_repository import OrderRepository
from infrastructure.repositories.catalog_repository import CatalogRepository
from application.dto.order_dto import (
    OrderCreateDTO,
    OrderResponseDTO,
    OrderSummaryDTO,
)

logger = logging.getLogger(__name__)


class OrderService:
    """
    Сервис для управления заказами.

    Orchestration layer - координирует работу между
    репозиториями и доменными объектами.
    """

    def __init__(
            self,
            order_repository: OrderRepository,
            catalog_repository: CatalogRepository,
    ):
        """
        Args:
            order_repository: Репозиторий заказов
            catalog_repository: Репозиторий каталога
        """
        self.order_repo = order_repository
        self.catalog_repo = catalog_repository

        logger.info("✅ OrderService initialized")

    def create_order_from_cart(
            self,
            cart: Cart,
            phone: str,
            address: str
    ) -> Order:
        """
        Создает заказ из корзины.

        Args:
            cart: Корзина покупателя
            phone: Телефон
            address: Адрес доставки

        Returns:
            Order: Созданный заказ

        Raises:
            ValueError: Если корзина пуста или данные невалидны
        """
        if cart.is_empty():
            raise ValueError("Cannot create order from empty cart")

        # Валидируем остатки
        errors = cart.validate_against_stock(
            lambda product_id: self.catalog_repo.get_stock(product_id)
        )

        if errors:
            raise ValueError(f"Stock validation failed: {'; '.join(errors)}")

        # Создаем OrderItem'ы из CartItem'ов
        order_items = []
        for cart_item in cart.get_items_list():
            order_items.append(
                OrderItem(
                    product_id=cart_item.product_id,
                    name=cart_item.name,
                    quantity=cart_item.quantity,
                    price=cart_item.price,
                )
            )

        # Создаем заказ
        order = Order(
            order_id=0,  # Будет присвоен в репозитории
            chat_id=cart.chat_id,
            items=order_items,
            phone=phone,
            address=address,
            status=OrderStatus.PENDING_PAYMENT_METHOD,
        )

        # Сохраняем
        saved_order = self.order_repo.save(order)

        logger.info(
            f"✅ Order #{saved_order.order_id} created "
            f"from cart (user: {cart.chat_id})"
        )

        return saved_order

    def set_payment_method(
            self,
            order_id: int,
            payment_method: PaymentMethod
    ) -> Order:
        """
        Устанавливает способ оплаты для заказа.

        Args:
            order_id: ID заказа
            payment_method: Способ оплаты

        Returns:
            Order: Обновленный заказ
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        order.set_payment_method(payment_method)
        updated_order = self.order_repo.update(order)

        logger.info(
            f"💳 Payment method set for order #{order_id}: "
            f"{payment_method.value}"
        )

        return updated_order

    def mark_as_paid(self, order_id: int, payment_details: dict) -> Order:
        """
        Отмечает заказ как оплаченный.

        Args:
            order_id: ID заказа
            payment_details: Детали платежа

        Returns:
            Order: Обновленный заказ
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        # Сохраняем Payment Intent ID если есть
        if 'payment_intent_id' in payment_details:
            order.set_stripe_payment_intent(payment_details['payment_intent_id'])

        order.update_status(OrderStatus.PAID)
        updated_order = self.order_repo.update(order)

        logger.info(f"✅ Order #{order_id} marked as PAID")

        return updated_order

    def confirm_order(self, order_id: int) -> Order:
        """
        Подтверждает заказ (менеджером).

        Args:
            order_id: ID заказа

        Returns:
            Order: Обновленный заказ
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        order.update_status(OrderStatus.CONFIRMED)
        updated_order = self.order_repo.update(order)

        logger.info(f"✅ Order #{order_id} confirmed by manager")

        return updated_order

    def mark_as_delivered(self, order_id: int) -> Order:
        """
        Отмечает заказ как доставленный и списывает товары.

        Args:
            order_id: ID заказа

        Returns:
            Order: Обновленный заказ
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        # Списываем товары со склада
        for item in order.items:
            success = self.catalog_repo.reduce_stock(
                item.product_id,
                item.quantity
            )
            if not success:
                logger.warning(
                    f"⚠️ Failed to reduce stock for product {item.product_id}"
                )

        order.update_status(OrderStatus.DELIVERED)
        updated_order = self.order_repo.update(order)

        logger.info(f"🚚 Order #{order_id} marked as DELIVERED")

        return updated_order

    def cancel_order(self, order_id: int, reason: str = None) -> Order:
        """
        Отменяет заказ.

        Args:
            order_id: ID заказа
            reason: Причина отмены (опционально)

        Returns:
            Order: Обновленный заказ
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        order.update_status(OrderStatus.CANCELLED, notes=reason)
        updated_order = self.order_repo.update(order)

        logger.info(f"❌ Order #{order_id} cancelled")

        return updated_order

    def get_user_orders(self, chat_id: int) -> List[Order]:
        """
        Получает все заказы пользователя.

        Args:
            chat_id: ID пользователя

        Returns:
            List[Order]: Список заказов
        """
        return self.order_repo.get_by_chat_id(chat_id)

    def get_pending_stripe_orders(self) -> List[Order]:
        """
        Получает заказы, ожидающие оплату через Stripe.

        Returns:
            List[Order]: Pending Stripe заказы
        """
        return self.order_repo.get_by_status_and_payment_method(
            OrderStatus.PENDING_PAYMENT,
            PaymentMethod.STRIPE
        )

    def create_order_from_dto(
            self,
            cart: Cart,
            dto: OrderCreateDTO,
    ) -> OrderResponseDTO:
        """
        Создаёт заказ из DTO и возвращает ResponseDTO.

        Обёртка над create_order_from_cart для работы с DTO.
        Используется в checkout_handler вместо прямого вызова
        create_order_from_cart(cart, phone, address).

        Args:
            cart: Корзина покупателя
            dto: Данные формы оформления

        Returns:
            OrderResponseDTO: Для передачи в Presentation layer
        """
        order = self.create_order_from_cart(
            cart=cart,
            phone=dto.phone,
            address=dto.address,
        )
        return OrderResponseDTO.from_order(order)

    def get_order_response_dto(
            self,
            order_id: int,
    ) -> Optional[OrderResponseDTO]:
        """
        Возвращает заказ в виде DTO.

        Используется когда handler хочет получить данные
        заказа без прямого доступа к доменному Order.

        Args:
            order_id: ID заказа

        Returns:
            Optional[OrderResponseDTO]
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            return None
        return OrderResponseDTO.from_order(order)

    def get_user_orders_summary(
            self,
            chat_id: int,
    ) -> List[OrderSummaryDTO]:
        """
        Возвращает краткий список заказов пользователя.

        Используется в разделе "📦 Мои заказы".

        Args:
            chat_id: ID пользователя

        Returns:
            List[OrderSummaryDTO]: Последние заказы
        """
        orders = self.order_repo.get_by_chat_id(chat_id)
        return [
            OrderSummaryDTO.from_order(o)
            for o in sorted(orders, key=lambda o: o.created_at, reverse=True)
        ]
