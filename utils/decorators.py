"""
Декораторы для обработки ошибок и повторных попыток.

Применение:
- error_handler: для Telegram callback/message handlers
- retry: для нестабильных внешних вызовов (Google Sheets, Stripe)
"""

import logging
import functools
import time
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


def error_handler(bot=None, default_message: str = "Произошла ошибка. Попробуйте позже."):
    """
    Декоратор для безопасной обработки ошибок в Telegram handlers.

    Перехватывает все исключения, логирует их и отправляет
    пользователю дружелюбное сообщение об ошибке.

    Args:
        bot: Инстанс telebot.TeleBot (для отправки сообщений)
        default_message: Сообщение об ошибке для пользователя

    Usage:
        @error_handler(bot=bot)
        def handle_start(message):
            ...

        @error_handler(bot=bot)
        def handle_callback(call):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"❌ Error in {func.__name__}: {e}",
                    exc_info=True
                )

                # Пробуем определить chat_id из аргументов
                chat_id = _extract_chat_id(args)

                # Отправляем сообщение об ошибке если есть bot и chat_id
                if bot and chat_id:
                    try:
                        bot.send_message(chat_id, default_message)
                    except Exception as send_error:
                        logger.error(
                            f"❌ Failed to send error message: {send_error}"
                        )

        return wrapper
    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Декоратор для повторных попыток при ошибках.

    Применяет экспоненциальный backoff между попытками.

    Args:
        max_attempts: Максимальное количество попыток
        delay: Начальная задержка между попытками (секунды)
        backoff: Множитель для увеличения задержки
        exceptions: Кортеж исключений для перехвата

    Usage:
        @retry(max_attempts=3, delay=1.0, exceptions=(ConnectionError,))
        def call_external_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"⚠️ {func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}"
                    )

                    if attempt < max_attempts:
                        logger.info(
                            f"⏳ Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff

            logger.error(
                f"❌ {func.__name__} failed after {max_attempts} attempts"
            )
            raise last_exception

        return wrapper
    return decorator


def _extract_chat_id(args: tuple) -> Optional[int]:
    """
    Извлекает chat_id из аргументов handler'а.

    Поддерживает Message и CallbackQuery объекты telebot.

    Args:
        args: Аргументы функции

    Returns:
        Optional[int]: chat_id если удалось определить
    """
    for arg in args:
        # telebot.types.Message
        if hasattr(arg, "chat") and hasattr(arg.chat, "id"):
            return arg.chat.id
        # telebot.types.CallbackQuery
        if hasattr(arg, "message") and hasattr(arg.message, "chat"):
            return arg.message.chat.id

    return None