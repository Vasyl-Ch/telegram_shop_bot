"""
Middleware for logging user actions."""

import logging
import telebot
from telebot import types

logger = logging.getLogger(__name__)


class LoggingMiddleware(telebot.BaseMiddleware):
    """
    Middleware for logging incoming messages and callbacks.

    Application of Single Responsibility:
    - Logging only
    - Does not interfere with business logic
    """

    def __init__(self):
        """Middleware initialization."""
        self.update_types = ["message", "callback_query"]
        super().__init__()

    def pre_process(self, message, data):
        """Logs the incoming message/callback before processing."""
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
        """Logs exceptions after processing."""
        if exception:
            logger.error(f"❌ Handler exception: {exception}", exc_info=True)
