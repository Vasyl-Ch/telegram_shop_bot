"""
Middleware для логирования действий пользователей.
"""

import logging
import telebot
from telebot import types

logger = logging.getLogger(__name__)


class LoggingMiddleware(telebot.BaseMiddleware):
    """
    Middleware для логирования входящих сообщений и callback'ов.

    Применение Single Responsibility:
    - Только логирование
    - Не вмешивается в бизнес-логику
    """

    def __init__(self):
        """Инициализация middleware."""
        self.update_types = ["message", "callback_query"]
        super().__init__()

    def pre_process(self, message, data):
        """Логирует входящее сообщение/callback до обработки."""
        if isinstance(message, types.Message):
            logger.info(
                f"📨 MSG | user={message.from_user.id} "
                f"(@{message.from_user.username}) | "
                f"text={repr(message.text)}"
            )
        elif isinstance(message, types.CallbackQuery):
            logger.info(
                f"🔘 CBQ | user={message.from_user.id} "
                f"(@{message.from_user.username}) | "
                f"data={repr(message.data)}"
            )

    def post_process(self, message, data, exception):
        """Логирует исключения после обработки."""
        if exception:
            logger.error(
                f"❌ Handler exception: {exception}",
                exc_info=True
            )