"""
Middleware for rate limiting.

Spam Protection: Limits the number of requests
from one user per unit of time.
"""

import time
from collections import defaultdict
from telebot import BaseMiddleware, types
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware to limit the request rate.

    Applying the Sliding Window Algorithm:
    - Tracks the user's last N requests
    - Blocks when the limit is exceeded
    - Automatically cleans up outdated records

    Args:
        max_requests: Maximum requests per time_window
        time_window: Time window (seconds)
    """

    def __init__(self, max_requests: int = 10, time_window: int = 10):
        """
        Middleware initialization.

        Args:
            max_requests: Request Limit (Default 10)
            time_window: Window in seconds (10 by default)
        """
        self.update_types = ["message", "callback_query"]
        self.max_requests = max_requests
        self.time_window = time_window

        self._requests: dict[int, list[float]] = defaultdict(list)

        super().__init__()

        logger.info(
            f"✅ RateLimitMiddleware initialized "
            f"(max: {max_requests} req/{time_window}s)"
        )

    def pre_process(self, message, data):
        """
        Checks the limit before processing the message.

        Args:
            message: Message or CallbackQuery
            data: Additional data

        Raises:
            Exception: When the limit is exceeded
        """
        user_id = self._get_user_id(message)
        if not user_id:
            return

        now = time.time()

        # ════════════════════════════════════════════════════════
        # Clearing Stale Records (Sliding Window)
        # ════════════════════════════════════════════════════════

        self._requests[user_id] = [
            ts for ts in self._requests[user_id] if now - ts < self.time_window
        ]

        # ════════════════════════════════════════════════════════
        # Checking the limit
        # ════════════════════════════════════════════════════════

        if len(self._requests[user_id]) >= self.max_requests:
            logger.warning(
                f"🚫 Rate limit exceeded: user {user_id} "
                f"({len(self._requests[user_id])} requests)"
            )

            self._send_limit_warning(message)

            raise Exception("Rate limit exceeded")

        # ════════════════════════════════════════════════════════
        # Log the current request
        # ════════════════════════════════════════════════════════

        self._requests[user_id].append(now)

    def post_process(self, message, data, exception):
        """Processing after the execution of the handler."""
        pass

    def _get_user_id(self, message) -> int:
        """
        Retrieves user_id from the message.

        Args:
            message: Message or CallbackQuery

        Returns:
            int: user ID or 0
        """
        if isinstance(message, types.Message):
            return message.from_user.id
        elif isinstance(message, types.CallbackQuery):
            return message.from_user.id
        return 0

    def _send_limit_warning(self, message):
        """
        Sends a warning when the limit is exceeded.

        Args:
            message: Message or CallbackQuery
        """
        try:
            warning_text = (
                "⚠️ <b>Слишком много запросов!</b>\n\n"
                f"Вы превысили лимит: {self.max_requests} запросов "
                f"за {self.time_window} секунд.\n\n"
                "Пожалуйста, подождите немного."
            )

            if isinstance(message, types.Message):
                message.bot.send_message(
                    message.chat.id, warning_text, parse_mode="HTML"
                )
            elif isinstance(message, types.CallbackQuery):
                message.bot.answer_callback_query(
                    message.id, "⚠️ Слишком много запросов. Подождите.", show_alert=True
                )
        except Exception as e:
            logger.error(f"Failed to send rate limit warning: {e}")
