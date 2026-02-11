"""
Репозиторий для корзин покупателей.

Реализация:
- In-memory хранилище
- Thread-safe
- Key: chat_id (ID пользователя)
"""

from typing import Optional
from threading import Lock
import logging

from infrastructure.repositories.base_repository import BaseRepository
from domain.entities.cart import Cart

logger = logging.getLogger(__name__)


class CartRepository(BaseRepository[Cart]):
    """
    In-memory репозиторий корзин.

    Использует chat_id как ключ (у каждого пользователя одна корзина).
    """

    def __init__(self):
        """Инициализация репозитория."""
        self._carts: dict[int, Cart] = {}
        self._lock = Lock()

        logger.info("✅ CartRepository initialized (in-memory)")

    def save(self, entity: Cart) -> Cart:
        """Сохраняет корзину."""
        with self._lock:
            self._carts[entity.chat_id] = entity
            return entity

    def get_by_id(self, entity_id: int) -> Optional[Cart]:
        """
        Получает корзину по chat_id.

        Args:
            entity_id: chat_id пользователя
        """
        with self._lock:
            return self._carts.get(entity_id)

    def get_all(self) -> list[Cart]:
        """Возвращает все корзины."""
        with self._lock:
            return list(self._carts.values())

    def update(self, entity: Cart) -> Cart:
        """Обновляет корзину."""
        with self._lock:
            self._carts[entity.chat_id] = entity
            return entity

    def delete(self, entity_id: int) -> bool:
        """Удаляет корзину."""
        with self._lock:
            if entity_id in self._carts:
                del self._carts[entity_id]
                return True
            return False

    def exists(self, entity_id: int) -> bool:
        """Проверяет существование корзины."""
        with self._lock:
            return entity_id in self._carts

    # Специфичные методы для Cart

    def get_or_create(self, chat_id: int) -> Cart:
        """
        Получает корзину или создает новую если не существует.

        Args:
            chat_id: ID пользователя

        Returns:
            Cart: Существующая или новая корзина
        """
        with self._lock:
            if chat_id not in self._carts:
                cart = Cart(chat_id=chat_id)
                self._carts[chat_id] = cart
                logger.info(f"🛒 New cart created for user {chat_id}")
            return self._carts[chat_id]

    def clear_cart(self, chat_id: int) -> None:
        """
        Очищает корзину пользователя.

        Args:
            chat_id: ID пользователя
        """
        with self._lock:
            if chat_id in self._carts:
                self._carts[chat_id].clear()
                logger.info(f"🗑️ Cart cleared for user {chat_id}")