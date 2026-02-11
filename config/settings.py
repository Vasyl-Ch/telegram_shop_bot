import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """
    Настройки приложения (immutable).

    Все настройки загружаются из переменных окружения и валидируются
    при старте приложения (fail-fast подход).
    """

    # Telegram Bot
    bot_token: str
    bot_username: str
    seller_chat_id: str

    # Google Sheets
    google_disk_id: str
    json_key_file: str

    # Stripe
    stripe_secret_key: str
    stripe_publishable_key: str

    # Polling настройки (для Stripe без webhook)
    payment_poll_interval: int  # секунды между проверками
    payment_max_age_hours: int  # не проверять заказы старше X часов

    # Application
    environment: str  # development / production
    log_level: str

    @classmethod
    def from_env(cls) -> 'Settings':
        """
        Загружает настройки из переменных окружения.

        Returns:
            Settings: Валидированные настройки

        Raises:
            ValueError: Если обязательные переменные отсутствуют
        """
        # Обязательные переменные
        required_vars = {
            'BOT_TOKEN': 'bot_token',
            'BOT_USERNAME': 'bot_username',
            'SELLER_CHAT_ID': 'seller_chat_id',
            'GOOGLE_DISK_ID': 'google_disk_id',
            'JSON_KEY_FILE': 'json_key_file',
            'STRIPE_SECRET_KEY': 'stripe_secret_key',
            'STRIPE_PUBLISHABLE_KEY': 'stripe_publishable_key',
        }

        config = {}
        missing = []

        # Валидация обязательных переменных
        for env_var, field_name in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(env_var)
            config[field_name] = value or ''

        if missing:
            raise ValueError(
                f"❌ Missing required environment variables: {', '.join(missing)}\n"
                f"Please check your .env file."
            )

        # Опциональные переменные с дефолтными значениями
        config['payment_poll_interval'] = int(
            os.getenv('PAYMENT_POLL_INTERVAL', '60')
        )
        config['payment_max_age_hours'] = int(
            os.getenv('PAYMENT_MAX_AGE_HOURS', '24')
        )
        config['environment'] = os.getenv('ENVIRONMENT', 'development')
        config['log_level'] = os.getenv('LOG_LEVEL', 'INFO')

        return cls(**config)

    @property
    def is_production(self) -> bool:
        """Проверка production окружения."""
        return self.environment.lower() == 'production'

    @property
    def is_development(self) -> bool:
        """Проверка development окружения."""
        return self.environment.lower() == 'development'


# Глобальный инстанс настроек (Singleton pattern)
# Создается один раз при импорте модуля
settings = Settings.from_env()
