"""
User Limit entity - management of user limits and bans.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UserLimit:
    """
    An entity to store information about the user's limits and bans.

    Attributes:
        chat_id: Telegram User ID
        is_banned: Is the user banned
        ban_reason: Ban Reason
        banned_at: Ban Installation Time
        order_limit_exceeded: Is the automatic order limit exceeded
        custom_limit_removed: Is the limit manually removed by the manager
    """

    chat_id: int
    is_banned: bool = False
    ban_reason: Optional[str] = None
    banned_at: Optional[datetime] = None
    order_limit_exceeded: bool = False
    custom_limit_removed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def ban_user(self, reason: str) -> None:
        """
    Bans the user.

    Args:
            reason: Reason for banning
        """
        self.is_banned = True
        self.ban_reason = reason
        self.banned_at = datetime.now()
        self.updated_at = datetime.now()

    def unban_user(self) -> None:
        """Removes the ban from the user."""
        self.is_banned = False
        self.ban_reason = None
        self.banned_at = None
        self.updated_at = datetime.now()

    def set_limit_exceeded(self) -> None:
        """Sets the flag for exceeding the automatic limit."""
        self.order_limit_exceeded = True
        self.updated_at = datetime.now()

    def remove_custom_limit(self) -> None:
        """Removes the limit manually (manager action)."""
        self.custom_limit_removed = True
        self.order_limit_exceeded = False
        self.updated_at = datetime.now()

    def reset_limit(self) -> None:
        """Resets all limits."""
        self.order_limit_exceeded = False
        self.custom_limit_removed = False
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to a dictionary for serialization."""
        return {
            "chat_id": self.chat_id,
            "is_banned": self.is_banned,
            "ban_reason": self.ban_reason,
            "banned_at": self.banned_at.isoformat() if self.banned_at else None,
            "order_limit_exceeded": self.order_limit_exceeded,
            "custom_limit_removed": self.custom_limit_removed,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
