import os
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """
    Application settings (immutable).

    All settings are loaded from environment variables and validated
    at application startup (fail-fast approach).
    """
    support_manager_id: str
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
    payment_poll_interval: int
    payment_max_age_hours: int

    # Application
    environment: str  # development / production
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        """
        Loads settings from environment variables.

        Returns:
            Settings: Validated settings

        Raises:
            ValueError: If required variables are missing
        """
        required_vars = {
            "BOT_TOKEN": "bot_token",
            "BOT_USERNAME": "bot_username",
            "SELLER_CHAT_ID": "seller_chat_id",
            "SUPPORT_MANAGER_ID": "support_manager_id",
            "GOOGLE_DISK_ID": "google_disk_id",
            "JSON_KEY_FILE": "json_key_file",
            "STRIPE_SECRET_KEY": "stripe_secret_key",
            "STRIPE_PUBLISHABLE_KEY": "stripe_publishable_key",
        }

        config = {}
        missing = []

        for env_var, field_name in required_vars.items():
            value = os.getenv(env_var)
            logger.info(f"🔍 Loading {env_var}: {repr(value)}")
            if not value:
                missing.append(env_var)
            config[field_name] = value or ""

        if missing:
            raise ValueError(
                f"❌ Missing required environment variables: {', '.join(missing)}\n"
                f"Please check your .env file."
            )

        config["payment_poll_interval"] = int(os.getenv("PAYMENT_POLL_INTERVAL", "60"))
        config["payment_max_age_hours"] = int(os.getenv("PAYMENT_MAX_AGE_HOURS", "24"))
        config["environment"] = os.getenv("ENVIRONMENT", "development")
        config["log_level"] = os.getenv("LOG_LEVEL", "INFO")

        return cls(**config)

    @property
    def is_production(self) -> bool:
        """Checking the production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Checking the development environment."""
        return self.environment.lower() == "development"


settings = Settings.from_env()
