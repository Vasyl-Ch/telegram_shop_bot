"""
Repository for shopping carts.

Implementation:
- In-memory storage
- Thread-safe
- Key: chat_id (User ID)
"""

from typing import Optional
from threading import Lock
import logging

from infrastructure.repositories.base_repository import BaseRepository
from domain.entities.cart import Cart

logger = logging.getLogger(__name__)


class CartRepository(BaseRepository[Cart]):
    """
    In-memory repositor.

    Uses chat_id as a key (each user has one bucket).
    """

    def __init__(self):
        """Initialize the repository."""
        self._carts: dict[int, Cart] = {}
        self._lock = Lock()

        logger.info("✅ CartRepository initialized (in-memory)")

    def save(self, entity: Cart) -> Cart:
        """Saves the trash."""
        with self._lock:
            self._carts[entity.chat_id] = entity
            return entity

    def get_by_id(self, entity_id: int) -> Optional[Cart]:
        """
        Gets a basket for chat_id.

        Args:
            entity_id: chat_id user
        """
        with self._lock:
            return self._carts.get(entity_id)

    def get_all(self) -> list[Cart]:
        """Returns all carts."""
        with self._lock:
            return list(self._carts.values())

    def update(self, entity: Cart) -> Cart:
        """Updates the cart."""
        with self._lock:
            self._carts[entity.chat_id] = entity
            return entity

    def delete(self, entity_id: int) -> bool:
        """Deletes the Recycle Bin."""
        with self._lock:
            if entity_id in self._carts:
                del self._carts[entity_id]
                return True
            return False

    def exists(self, entity_id: int) -> bool:
        """Checks for the existence of the Recycle Bin."""
        with self._lock:
            return entity_id in self._carts

    def get_or_create(self, chat_id: int) -> Cart:
        """
        Retrieves the cart or creates a new one if it doesn't exist.

        Args:
            chat_id: User ID

        Returns:
            Cart: Existing or new cart
        """
        with self._lock:
            if chat_id not in self._carts:
                cart = Cart(chat_id=chat_id)
                self._carts[chat_id] = cart
                logger.info(f"🛒 New cart created for user {chat_id}")
            return self._carts[chat_id]

    def clear_cart(self, chat_id: int) -> None:
        """
        Empties the user's Recycle Bin.

        Args:
            chat_id: User ID
        """
        with self._lock:
            if chat_id in self._carts:
                self._carts[chat_id].clear()
                logger.info(f"🗑️ Cart cleared for user {chat_id}")
