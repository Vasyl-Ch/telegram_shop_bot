import logging
from typing import Optional
from collections import OrderedDict
from datetime import datetime, timedelta
import telebot

from application.dto import CheckoutStateDTO

logger = logging.getLogger(__name__)


def get_customer_name(bot: telebot.TeleBot, chat_id: int) -> str:
    """
    Получает имя покупателя из Telegram.

    Args:
        bot: Инстанс бота
        chat_id: ID пользователя

    Returns:
        str: Имя пользователя или fallback
    """
    try:
        user = bot.get_chat(chat_id)
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return name or user.username or f"ID:{chat_id}"
    except Exception as e:
        logger.warning(f"Could not get customer name for {chat_id}: {e}")
        return f"ID:{chat_id}"


class TTLCache:
    """TTL-кеш с автоматической очисткой устаревших записей."""

    def __init__(self, ttl_minutes: int = 30):
        self._cache: OrderedDict[int, tuple[CheckoutStateDTO, datetime]] = OrderedDict()
        self._ttl = timedelta(minutes=ttl_minutes)

    def set(self, key: int, value: CheckoutStateDTO) -> None:
        """Добавляет или обновляет значение."""
        self._cleanup()  # Очистка при каждой записи
        self._cache[key] = (value, datetime.now())

    def get(self, key: int) -> Optional[CheckoutStateDTO]:
        """Возвращает значение, если не истекло."""
        self._cleanup()

        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if datetime.now() - timestamp > self._ttl:
            del self._cache[key]
            return None

        return value

    def pop(self, key: int, default=None) -> CheckoutStateDTO:
        """Удаляет и возвращает значение."""
        if key in self._cache:
            value, _ = self._cache.pop(key)
            return value
        return default

    def _cleanup(self) -> None:
        """Удаляет устаревшие записи."""
        now = datetime.now()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if now - timestamp > self._ttl
        ]

        for key in expired_keys:
            del self._cache[key]


