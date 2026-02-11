"""
Repository for orders.

Implementation:
- In-memory storage (can be replaced with a database)
- Thread-safe operations (Lock)
- Auto-increment for order IDs

Why in-memory:
- Quick start without database configuration
- Easy to migrate to SQLite/PostgreSQL later
- Sufficient for light/medium loads
"""

from datetime import datetime
import json
from decimal import Decimal
from pathlib import Path
from typing import List, Optional
from threading import Lock
import logging

from infrastructure.repositories.base_repository import BaseRepository
from domain.entities.order import Order, OrderItem
from domain.enums.order_status import OrderStatus
from domain.enums.payment_method import PaymentMethod

logger = logging.getLogger(__name__)


class OrderRepository(BaseRepository[Order]):
    """
    In-memory repository of orders.

    Thread-safe through the use of Lock.
    """

    def __init__(self, persistence_file: str = "data/orders.json"):
        self._orders: dict[int, Order] = {}
        self._lock = Lock()
        self._next_id = 1
        self._persistence_file = Path(persistence_file)

        self._load_from_disk()

        logger.info(
            f"✅ OrderRepository initialized "
            f"({len(self._orders)} orders loaded from {persistence_file})"
        )

    def _load_from_disk(self) -> None:
        """Loads orders from a JSON file."""
        if not self._persistence_file.exists():
            logger.info("📁 No persistence file found, starting fresh")
            return

        try:
            with open(self._persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for order_data in data.get("orders", []):
                order = self._deserialize_order(order_data)
                self._orders[order.order_id] = order

                if order.order_id >= self._next_id:
                    self._next_id = order.order_id + 1

            logger.info(f"✅ Loaded {len(self._orders)} orders from disk")

        except Exception as e:
            logger.error(f"❌ Error loading orders: {e}", exc_info=True)

    def _save_to_disk(self) -> None:
        """Saves orders to a JSON file."""
        try:
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "orders": [order.to_dict() for order in self._orders.values()],
                "last_updated": datetime.now().isoformat(),
            }

            temp_file = self._persistence_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            try:
                temp_file.replace(self._persistence_file)
            except PermissionError:
                logger.warning("⚠️ Permission denied for atomic replace, using direct write")
                with open(self._persistence_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                try:
                    temp_file.unlink()
                except:
                    pass

            logger.debug(f"💾 Saved {len(self._orders)} orders to disk")

        except Exception as e:
            logger.error(f"❌ Error saving orders: {e}", exc_info=True)

    def _deserialize_order(self, data: dict) -> Order:
        """Restores Order from the dictionary."""
        items = [
            OrderItem(
                product_id=item["product_id"],
                name=item["name"],
                quantity=item["quantity"],
                price=Decimal(str(item["price"])),
            )
            for item in data["items"]
        ]

        order = Order(
            order_id=data["order_id"],
            chat_id=data["chat_id"],
            items=items,
            phone=data["phone"],
            address=data["address"],
            status=OrderStatus(data["status"]),
            payment_method=(
                PaymentMethod(data["payment_method"])
                if data.get("payment_method")
                else None
            ),
            stripe_session_id=data.get("stripe_session_id"),
            stripe_payment_intent_id=data.get("stripe_payment_intent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            notes=data.get("notes"),
        )

        order.seller_message_id = data.get("seller_message_id")
        order.customer_message_id = data.get("customer_message_id")

        return order

    def _generate_id(self) -> int:
        """
        Generates a unique ID for a new order.

        Returns:
            int: New ID
        """
        order_id = self._next_id
        self._next_id += 1
        return order_id

    def save(self, entity: Order) -> Order:
        """Saves the order to memory AND to disk."""
        with self._lock:
            if entity.order_id == 0:
                from copy import copy

                new_id = self._generate_id()
                saved_order = copy(entity)
                saved_order.order_id = new_id
                self._orders[new_id] = saved_order

                self._save_to_disk()

                logger.info(f"💾 Order #{new_id} saved")
                return saved_order
            else:
                self._orders[entity.order_id] = entity

                self._save_to_disk()

                logger.info(f"💾 Order #{entity.order_id} updated")
                return entity

    def get_by_id(self, entity_id: int) -> Optional[Order]:
        """Receives the order by ID."""
        with self._lock:
            return self._orders.get(entity_id)

    def get_all(self) -> List[Order]:
        """Returns all orders."""
        with self._lock:
            return list(self._orders.values())

    def update(self, entity: Order) -> Order:
        """Updates the order in memory AND on disk."""
        with self._lock:
            if entity.order_id not in self._orders:
                raise ValueError(f"Order #{entity.order_id} not found")

            self._orders[entity.order_id] = entity

            self._save_to_disk()

            logger.info(f"🔄 Order #{entity.order_id} updated")
            return entity

    def delete(self, entity_id: int) -> bool:
        """Deletes the order from memory AND from disk."""
        with self._lock:
            if entity_id in self._orders:
                del self._orders[entity_id]

                self._save_to_disk()

                logger.info(f"🗑️ Order #{entity_id} deleted")
                return True
            return False

    def exists(self, entity_id: int) -> bool:
        """Checks the existence of the order."""
        with self._lock:
            return entity_id in self._orders

    def get_by_chat_id(self, chat_id: int) -> List[Order]:
        """
        Receives all the user's orders.

        Args:
            chat_id: Telegram User ID

        Returns:
            List[Order]: A list of the user's orders
        """
        with self._lock:
            return [
                order for order in self._orders.values() if order.chat_id == chat_id
            ]

    def get_by_status(self, status: OrderStatus) -> List[Order]:
        """
        Receives orders with a certain status.

        Args:
            status: Order status

        Returns:
            List[Order]: List of orders with this status
        """
        with self._lock:
            return [order for order in self._orders.values() if order.status == status]

    def get_by_status_and_payment_method(
        self, status: OrderStatus, payment_method: PaymentMethod
    ) -> List[Order]:
        """
        Receives orders with a specific status and payment method.

        Used for polling - receiving pending Stripe orders.

        Args:
            status: Order status
            payment_method: Payment Method

        Returns:
            List[Order]: Filtered orders
        """
        with self._lock:
            return [
                order
                for order in self._orders.values()
                if order.status == status and order.payment_method == payment_method
            ]

    def get_by_stripe_session_id(self, session_id: str) -> Optional[Order]:
        """
        Finds an order by Stripe Session ID.

        Args:
            session_id: ID Stripe Checkout Session

        Returns:
            Optional[Order]: Order if found
        """
        with self._lock:
            for order in self._orders.values():
                if order.stripe_session_id == session_id:
                    return order
            return None

    def get_pending_orders(self) -> List[Order]:
        """
        Receives orders that are waiting to be processed.

        Returns:
            List[Order]: Pending orders
        """
        with self._lock:
            return [order for order in self._orders.values() if not order.is_final()]

    def count_by_status(self, status: OrderStatus) -> int:
        """
        Counts the number of orders with a certain status.

        Args:
            status: Order status

        Returns:
            int: Number of orders
        """
        with self._lock:
            return sum(1 for order in self._orders.values() if order.status == status)
