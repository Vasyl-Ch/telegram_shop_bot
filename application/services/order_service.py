"""
Order Service - orchestration of the business logic of orders.

Applications of SOLID:
- Single Responsibility: Order logic only
- Dependency Injection: all dependencies through the constructor
- Interface Segregation: Uses only the necessary repository methods
"""

import logging
from typing import List, Optional

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
    Order management service.

    Orchestration layer - coordinates work between
    repositories and domain objects.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        catalog_repository: CatalogRepository,
    ):
        """
        Args:
            order_repository: Order Repository
            catalog_repository: Directory Repository
        """
        self.order_repo = order_repository
        self.catalog_repo = catalog_repository

        logger.info("✅ OrderService initialized")

    def create_order_from_cart(self, cart: Cart, phone: str, address: str) -> Order:
        """
        Creates an order from the cart.

        Args:
            cart: Shopping cart
            phone: Phone
            address: Delivery address

        Returns:
            Order: Created order

        Raises:
            ValueError: If the cart is empty or the data is invalid
        """
        if cart.is_empty():
            raise ValueError("Cannot create order from empty cart")

        errors = cart.validate_against_stock(
            lambda product_id: self.catalog_repo.get_stock(product_id)
        )

        if errors:
            raise ValueError(f"Stock validation failed: {'; '.join(errors)}")

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

        order = Order(
            order_id=0,
            chat_id=cart.chat_id,
            items=order_items,
            phone=phone,
            address=address,
            status=OrderStatus.PENDING_PAYMENT_METHOD,
        )

        saved_order = self.order_repo.save(order)

        logger.info(
            f"✅ Order #{saved_order.order_id} created "
            f"from cart (user: {cart.chat_id})"
        )

        return saved_order

    def set_payment_method(self, order_id: int, payment_method: PaymentMethod) -> Order:
        """
        Sets the payment method for the order.

        Args:
            order_id: Order ID
            payment_method: Payment Method

        Returns:
            Order: Updated order
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        order.set_payment_method(payment_method)
        updated_order = self.order_repo.update(order)

        logger.info(
            f"💳 Payment method set for order #{order_id}: " f"{payment_method.value}"
        )

        return updated_order

    def mark_as_paid(self, order_id: int, payment_details: dict) -> Order:
        """
        Marks the order as paid.

        Args:
            order_id: Order ID
            payment_details: Payment Details

        Returns:
            Order: Updated order
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        if "payment_intent_id" in payment_details:
            order.set_stripe_payment_intent(payment_details["payment_intent_id"])

        order.update_status(OrderStatus.PAID)
        updated_order = self.order_repo.update(order)

        logger.info(f"✅ Order #{order_id} marked as PAID")

        return updated_order

    def confirm_order(self, order_id: int) -> Order:
        """
        Confirms the order (by the manager).

        Args:
            order_id: Order ID

        Returns:
            Order: Updated order
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
        Marks the order as delivered and writes off the goods.

        Args:
            order_id: Order ID

        Returns:
            Order: Updated order
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order #{order_id} not found")

        for item in order.items:
            success = self.catalog_repo.reduce_stock(item.product_id, item.quantity)
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
        Cancels the order.

        Args:
            order_id: Order ID
            reason: Reason for cancellation (optional)

        Returns:
            Order: Updated order
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
        Receives all the user's orders.

        Args:
            chat_id: User ID

        Returns:
            List[Order]: List of orders
        """
        return self.order_repo.get_by_chat_id(chat_id)

    def get_pending_stripe_orders(self) -> List[Order]:
        """
        Receives orders waiting to be paid via Stripe.

        Returns:
            List[Order]: Pending Stripe Orders
        """
        return self.order_repo.get_by_status_and_payment_method(
            OrderStatus.PENDING_PAYMENT, PaymentMethod.STRIPE
        )

    def create_order_from_dto(
        self,
        cart: Cart,
        dto: OrderCreateDTO,
    ) -> OrderResponseDTO:
        """
        Creates an order from the DTO and returns the ResponseDTO.

        Wrapper over the create_order_from_cart for working with DTO.
        Used in checkout_handler instead of a direct call
        create_order_from_cart(cart, phone, address).

        Args:
            cart: Shopping cart
            dto: Form data

        Returns:
            OrderResponseDTO: To pass to the Presentation layer
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
        Returns the order as a DTO.

        Used when handler wants to retrieve data
        order without direct access to the domain Order.

        Args:
            order_id: Order ID

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
        Returns a short list of the user's orders.

        Used in the My 📦 Orders section.

        Args:
            chat_id: User ID

        Returns:
            List[OrderSummaryDTO]: Recent Orders
        """
        orders = self.order_repo.get_by_chat_id(chat_id)
        return [
            OrderSummaryDTO.from_order(o)
            for o in sorted(orders, key=lambda o: o.created_at, reverse=True)
        ]
