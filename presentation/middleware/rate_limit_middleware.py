"""
Middleware для rate limiting.

Защита от spam-атак: ограничивает количество запросов
от одного пользователя за единицу времени.
"""

import time
from collections import defaultdict
from telebot import BaseMiddleware, types
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов.

    Применение Sliding Window Algorithm:
    - Отслеживает последние N запросов пользователя
    - Блокирует при превышении лимита
    - Автоматически очищает устаревшие записи

    Args:
        max_requests: Максимум запросов за time_window
        time_window: Временное окно (секунды)
    """

    def __init__(self, max_requests: int = 10, time_window: int = 10):
        """
        Инициализация middleware.

        Args:
            max_requests: Лимит запросов (по умолчанию 10)
            time_window: Окно в секундах (по умолчанию 10)
        """
        self.update_types = ["message", "callback_query"]
        self.max_requests = max_requests
        self.time_window = time_window

        # Хранилище: {user_id: [timestamp1, timestamp2, ...]}
        self._requests: dict[int, list[float]] = defaultdict(list)

        super().__init__()

        logger.info(
            f"✅ RateLimitMiddleware initialized "
            f"(max: {max_requests} req/{time_window}s)"
        )

    def pre_process(self, message, data):
        """
        Проверяет лимит перед обработкой сообщения.

        Args:
            message: Message или CallbackQuery
            data: Дополнительные данные

        Raises:
            Exception: При превышении лимита
        """
        user_id = self._get_user_id(message)
        if not user_id:
            return

        now = time.time()

        # ════════════════════════════════════════════════════════
        # Очистка устаревших записей (Sliding Window)
        # ════════════════════════════════════════════════════════

        self._requests[user_id] = [
            ts for ts in self._requests[user_id]
            if now - ts < self.time_window
        ]

        # ════════════════════════════════════════════════════════
        # Проверка лимита
        # ════════════════════════════════════════════════════════

        if len(self._requests[user_id]) >= self.max_requests:
            logger.warning(
                f"🚫 Rate limit exceeded: user {user_id} "
                f"({len(self._requests[user_id])} requests)"
            )

            # Отправляем уведомление пользователю
            self._send_limit_warning(message)

            # Блокируем дальнейшую обработку
            raise Exception("Rate limit exceeded")

        # ════════════════════════════════════════════════════════
        # Регистрируем текущий запрос
        # ════════════════════════════════════════════════════════

        self._requests[user_id].append(now)

    def post_process(self, message, data, exception):
        """Обработка после выполнения handler'а."""
        pass

    def _get_user_id(self, message) -> int:
        """
        Извлекает user_id из сообщения.

        Args:
            message: Message или CallbackQuery

        Returns:
            int: ID пользователя или 0
        """
        if isinstance(message, types.Message):
            return message.from_user.id
        elif isinstance(message, types.CallbackQuery):
            return message.from_user.id
        return 0

    def _send_limit_warning(self, message):
        """
        Отправляет предупреждение о превышении лимита.

        Args:
            message: Message или CallbackQuery
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
                    message.chat.id,
                    warning_text,
                    parse_mode="HTML"
                )
            elif isinstance(message, types.CallbackQuery):
                message.bot.answer_callback_query(
                    message.id,
                    "⚠️ Слишком много запросов. Подождите.",
                    show_alert=True
                )
        except Exception as e:
            logger.error(f"Failed to send rate limit warning: {e}")