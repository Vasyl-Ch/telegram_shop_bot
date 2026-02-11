import logging
from typing import Optional
from collections import OrderedDict
from datetime import datetime, timedelta
import telebot

from application.dto import CheckoutStateDTO

logger = logging.getLogger(__name__)


def get_customer_name(bot: telebot.TeleBot, chat_id: int) -> str:
    """
    Gets the buyer's name from Telegram.

    Args:
        bot: Bot instance
        chat_id: User ID

    Returns:
        str: Username or fallback
    """
    try:
        user = bot.get_chat(chat_id)
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return name or user.username or f"ID:{chat_id}"
    except Exception as e:
        logger.warning(f"Could not get customer name for {chat_id}: {e}")
        return f"ID:{chat_id}"


class TTLCache:
    """TTL cache with automatic cleanup of stale entries."""

    def __init__(self, ttl_minutes: int = 30):
        self._cache: OrderedDict[int, tuple[CheckoutStateDTO, datetime]] = OrderedDict()
        self._ttl = timedelta(minutes=ttl_minutes)

    def __setitem__(self, key: int, value: CheckoutStateDTO) -> None:
        """Allows dict-style assignment: cache[key] = value"""
        self.set(key, value)

    def __getitem__(self, key: int) -> Optional[CheckoutStateDTO]:
        """Allows dict-style access: cache[key]"""
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result

    def __contains__(self, key: int) -> bool:
        """Allows 'key in cache' checks"""
        return self.get(key) is not None

    def set(self, key: int, value: CheckoutStateDTO) -> None:
        """Adds or updates a value."""
        self._cleanup()
        self._cache[key] = (value, datetime.now())

    def get(self, key: int) -> Optional[CheckoutStateDTO]:
        """Returns a value if it has not expired."""
        self._cleanup()

        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if datetime.now() - timestamp > self._ttl:
            del self._cache[key]
            return None

        return value

    def pop(self, key: int, default=None) -> CheckoutStateDTO:
        """Deletes and returns a value."""
        if key in self._cache:
            value, _ = self._cache.pop(key)
            return value
        return default

    def items(self):
        """Returns items for iteration"""
        self._cleanup()
        return [(k, v) for k, (v, _) in self._cache.items()]

    def _cleanup(self) -> None:
        """Deletes obsolete records."""
        now = datetime.now()
        expired_keys = [
            key
            for key, (_, timestamp) in self._cache.items()
            if now - timestamp > self._ttl
        ]

        for key in expired_keys:
            del self._cache[key]
