"""
Репозиторий для заказов.

Реализация:
- In-memory хранилище (можно заменить на БД)
- Thread-safe операции (Lock)
- Auto-increment для ID заказов

Почему in-memory:
- Быстрый старт без настройки БД
- Легко мигрировать на SQLite/PostgreSQL позже
- Достаточно для малых/средних нагрузок
"""

from typing import List, Optional
from threading import Lock
import logging
from copy import copy

from infrastructure.repositories.base_repository import BaseRepository
from domain.entities.order import Order
from domain.enums.order_status import OrderStatus
from domain.enums.payment_method import PaymentMethod

logger = logging.getLogger(__name__)


class OrderRepository(BaseRepository[Order]):
    """
    In-memory репозиторий заказов.

    Thread-safe благодаря использованию Lock.
    """

    def __init__(self):
        """Инициализация репозитория."""
        self._orders: dict[int, Order] = {}
        self._lock = Lock()
        self._next_id = 1

        logger.info("✅ OrderRepository initialized (in-memory)")

    def _generate_id(self) -> int:
        """
        Генерирует уникальный ID для нового заказа.

        Returns:
            int: Новый ID
        """
        order_id = self._next_id
        self._next_id += 1
        return order_id

    def save(self, entity: Order) -> Order:
        with self._lock:
            if entity.order_id == 0:
                new_id = self._generate_id()
                saved_order = copy(entity)
                saved_order.order_id = new_id
                self._orders[new_id] = saved_order
                logger.info(f"💾 Order #{new_id} saved")
                return saved_order
            else:
                self._orders[entity.order_id] = entity
                logger.info(f"💾 Order #{entity.order_id} saved")
                return entity

    def get_by_id(self, entity_id: int) -> Optional[Order]:
        """Получает заказ по ID."""
        with self._lock:
            return self._orders.get(entity_id)

    def get_all(self) -> List[Order]:
        """Возвращает все заказы."""
        with self._lock:
            return list(self._orders.values())

    def update(self, entity: Order) -> Order:
        """
        Обновляет существующий заказ.

        Raises:
            ValueError: Если заказ не найден
        """
        with self._lock:
            if entity.order_id not in self._orders:
                raise ValueError(f"Order #{entity.order_id} not found")

            self._orders[entity.order_id] = entity
            logger.info(f"🔄 Order #{entity.order_id} updated")
            return entity

    def delete(self, entity_id: int) -> bool:
        """Удаляет заказ (обычно не используется в production)."""
        with self._lock:
            if entity_id in self._orders:
                del self._orders[entity_id]
                logger.info(f"🗑️ Order #{entity_id} deleted")
                return True
            return False

    def exists(self, entity_id: int) -> bool:
        """Проверяет существование заказа."""
        with self._lock:
            return entity_id in self._orders

    # Дополнительные методы специфичные для Order

    def get_by_chat_id(self, chat_id: int) -> List[Order]:
        """
        Получает все заказы пользователя.

        Args:
            chat_id: ID пользователя в Telegram

        Returns:
            List[Order]: Список заказов пользователя
        """
        with self._lock:
            return [
                order for order in self._orders.values()
                if order.chat_id == chat_id
            ]

    def get_by_status(self, status: OrderStatus) -> List[Order]:
        """
        Получает заказы с определенным статусом.

        Args:
            status: Статус заказа

        Returns:
            List[Order]: Список заказов с этим статусом
        """
        with self._lock:
            return [
                order for order in self._orders.values()
                if order.status == status
            ]

    def get_by_status_and_payment_method(
            self,
            status: OrderStatus,
            payment_method: PaymentMethod
    ) -> List[Order]:
        """
        Получает заказы с определенным статусом и способом оплаты.

        Используется для polling - получение pending Stripe заказов.

        Args:
            status: Статус заказа
            payment_method: Способ оплаты

        Returns:
            List[Order]: Отфильтрованные заказы
        """
        with self._lock:
            return [
                order for order in self._orders.values()
                if order.status == status and order.payment_method == payment_method
            ]

    def get_by_stripe_session_id(self, session_id: str) -> Optional[Order]:
        """
        Находит заказ по Stripe Session ID.

        Args:
            session_id: ID Stripe Checkout Session

        Returns:
            Optional[Order]: Заказ если найден
        """
        with self._lock:
            for order in self._orders.values():
                if order.stripe_session_id == session_id:
                    return order
            return None

    def get_pending_orders(self) -> List[Order]:
        """
        Получает заказы, ожидающие обработки.

        Returns:
            List[Order]: Незавершенные заказы
        """
        with self._lock:
            return [
                order for order in self._orders.values()
                if not order.is_final()
            ]

    def count_by_status(self, status: OrderStatus) -> int:
        """
        Подсчитывает количество заказов с определенным статусом.

        Args:
            status: Статус заказа

        Returns:
            int: Количество заказов
        """
        with self._lock:
            return sum(
                1 for order in self._orders.values()
                if order.status == status
            )