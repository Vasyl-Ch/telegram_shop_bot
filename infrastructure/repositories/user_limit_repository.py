"""
Repository to manage user limits and bans."""

import json
import logging
from pathlib import Path
from typing import Optional, List
from threading import Lock
from datetime import datetime
import os

from domain.entities.user_limit import UserLimit

logger = logging.getLogger(__name__)


class UserLimitRepository:
    """
    In-memory repository of user limits with persistence.
    """

    def __init__(self, persistence_file: str = "data/user_limits.json"):
        """
        Args:
            persistence_file: File path to save data
        """
        self._limits: dict[int, UserLimit] = {}
        self._lock = Lock()
        self._persistence_file = Path(persistence_file)

        self._load_from_disk()

        logger.info(
            f"✅ UserLimitRepository initialized "
            f"({len(self._limits)} user limits loaded)"
        )

    def _load_from_disk(self) -> None:
        """Loads limits from a JSON file."""
        if not self._persistence_file.exists():
            logger.info("📁 No user limits file found, starting fresh")
            return

        try:
            with open(self._persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for limit_data in data.get("limits", []):
                limit = self._deserialize_limit(limit_data)
                self._limits[limit.chat_id] = limit

            logger.info(f"✅ Loaded {len(self._limits)} user limits from disk")

        except Exception as e:
            logger.error(f"❌ Error loading user limits: {e}", exc_info=True)

    def _save_to_disk(self) -> None:
        """Saves limits to a JSON file."""
        try:
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "limits": [limit.to_dict() for limit in self._limits.values()],
                "last_updated": datetime.now().isoformat(),
            }

            temp_file = self._persistence_file.with_suffix(".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            try:
                if self._persistence_file.exists():
                    self._persistence_file.unlink()

                temp_file.rename(self._persistence_file)

            except PermissionError:
                logger.warning("⚠️ Could not use atomic write, using direct write")
                with open(self._persistence_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass

            logger.debug(f"💾 Saved {len(self._limits)} user limits to disk")

        except Exception as e:
            logger.error(f"❌ Error saving user limits: {e}", exc_info=True)

    def _deserialize_limit(self, data: dict) -> UserLimit:
        """Restores UserLimit from the dictionary."""
        return UserLimit(
            chat_id=data["chat_id"],
            is_banned=data.get("is_banned", False),
            ban_reason=data.get("ban_reason"),
            banned_at=(
                datetime.fromisoformat(data["banned_at"])
                if data.get("banned_at")
                else None
            ),
            order_limit_exceeded=data.get("order_limit_exceeded", False),
            custom_limit_removed=data.get("custom_limit_removed", False),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def get_or_create(self, chat_id: int) -> UserLimit:
        """
        Receives or creates a limit for the user.

        Args:
            chat_id: User ID

        Returns:
            UserLimit: User limit
        """
        with self._lock:
            if chat_id not in self._limits:
                limit = UserLimit(chat_id=chat_id)
                self._limits[chat_id] = limit
                self._save_to_disk()
                logger.info(f"📝 Created new user limit for {chat_id}")
            return self._limits[chat_id]

    def update(self, limit: UserLimit) -> UserLimit:
        """
        Updates the user's limit.

        Args:
            limit: Updated limit

        Returns:
            UserLimit: Saved Limit
        """
        with self._lock:
            self._limits[limit.chat_id] = limit
            self._save_to_disk()
            logger.info(f"🔄 Updated user limit for {limit.chat_id}")
            return limit

    def get(self, chat_id: int) -> Optional[UserLimit]:
        """
        Gets the user's limit.

        Args:
            chat_id: User ID

        Returns:
            Optional[UserLimit]: Limit or None
        """
        with self._lock:
            return self._limits.get(chat_id)

    def is_banned(self, chat_id: int) -> bool:
        """
        Checks if the user is banned.

        Args:
            chat_id: User ID

        Returns:
            bool: True if banned
        """
        limit = self.get(chat_id)
        return limit.is_banned if limit else False

    def get_all_banned(self) -> List[UserLimit]:
        """
        Gets all banned users.

        Returns:
            List[UserLimit]: List of banned
        """
        with self._lock:
            return [limit for limit in self._limits.values() if limit.is_banned]

    def get_all_with_limits(self) -> List[UserLimit]:
        """
        Gets all users with active limits.

        Returns:
            List[UserLimit]: List of users with limits
        """
        with self._lock:
            return [
                limit
                for limit in self._limits.values()
                if limit.order_limit_exceeded and not limit.custom_limit_removed
            ]
