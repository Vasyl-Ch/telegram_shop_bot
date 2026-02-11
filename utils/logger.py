"""
Настройка системы логирования.

Централизованная конфигурация логгеров для всего приложения.
"""

import logging
import sys
from typing import Optional


def setup_logging(log_level: str = "INFO") -> None:
    """
    Настраивает систему логирования для всего приложения.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Форматтер с подробной информацией
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler для stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Убираем дублирующиеся handlers
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Глушим лишние логи от сторонних библиотек
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("telebot").setLevel(logging.WARNING)
    logging.getLogger("stripe").setLevel(logging.WARNING)
    logging.getLogger("gspread").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает именованный логгер.

    Args:
        name: Имя логгера (обычно __name__)

    Returns:
        logging.Logger: Настроенный логгер
    """
    return logging.getLogger(name)