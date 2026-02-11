"""
Decorators for error handling and retry.

Application:
- error_handler: for Telegram callback/message handlers
- retry: for unstable external calls (Google Sheets, Stripe)
"""

import logging
import functools
import time
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


def error_handler(
    bot=None, default_message: str = "Произошла ошибка. Попробуйте позже."
):
    """
    Decorator for safe error handling in Telegram handlers.

    Catches all exceptions, logs them, and sends them
    user-friendly error message.

    Args:
        bot: Telebot instance. TeleBot (for sending messages)
        default_message: Error message to the user

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
                logger.error(f"❌ Error in {func.__name__}: {e}", exc_info=True)

                chat_id = _extract_chat_id(args)

                if bot and chat_id:
                    try:
                        bot.send_message(chat_id, default_message)
                    except Exception as send_error:
                        logger.error(f"❌ Failed to send error message: {send_error}")

        return wrapper

    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for retries in case of errors.

    Applies exponential backoff between attempts.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts (seconds)
        backoff: Multiplier to increase latency
        exceptions: Tuple of exceptions to catch

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
                        logger.info(f"⏳ Retrying in {current_delay:.1f}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff

            logger.error(f"❌ {func.__name__} failed after {max_attempts} attempts")
            raise last_exception

        return wrapper

    return decorator


def _extract_chat_id(args: tuple) -> Optional[int]:
    """
    Extracts chat_id from handler arguments.

    Supports Message and CallbackQuery telebot objects.

    Args:
        args: Function Arguments

    Returns:
        Optional[int]: chat_id if the
    """
    for arg in args:
        if hasattr(arg, "chat") and hasattr(arg.chat, "id"):
            return arg.chat.id
        if hasattr(arg, "message") and hasattr(arg.message, "chat"):
            return arg.message.chat.id

    return None
