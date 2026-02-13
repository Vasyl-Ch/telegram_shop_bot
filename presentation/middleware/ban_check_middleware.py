"""
Middleware to check the ban of users.
"""

import logging
from telebot import BaseMiddleware, types

logger = logging.getLogger(__name__)


class BanCheckMiddleware(BaseMiddleware):
    """
    Middleware to check the user's ban before processing the message.

    Blocks access to all bot functions for banned users.
    """

    def __init__(self, user_limit_repo):
        """
        Middleware initialization.

        Args:
            user_limit_repo: User Limit Repository
        """
        self.update_types = ["message", "callback_query"]
        self.user_limit_repo = user_limit_repo

        self.allowed_commands = {"/start", "/help"}

        super().__init__()
        logger.info("✅ BanCheckMiddleware initialized")

    def pre_process(self, message, data):
        """
        Checks the ban before processing the message.

        Args:
            message: Message or CallbackQuery
            data: Additional data

        Raises:
            Exception: If the user is banned
        """
        user_id = self._get_user_id(message)
        if not user_id:
            return

        if isinstance(message, types.Message):
            if message.text and message.text.split()[0] in self.allowed_commands:

                return

        if self.user_limit_repo.is_banned(user_id):
            limit = self.user_limit_repo.get(user_id)

            ban_message = (
                "🚫 <b>Доступ к боту заблокирован</b>\n\n"
                f"<b>Причина:</b> {limit.ban_reason or 'не указана'}\n\n"
            )

            if limit.banned_at:
                ban_date = limit.banned_at.strftime("%d.%m.%Y %H:%M")
                ban_message += f"<b>Дата блокировки:</b> {ban_date}\n\n"

            ban_message += (
                "Для разблокировки свяжитесь с администратором.\n"
                "Используйте кнопку '💬 Связаться с менеджером' в главном меню."
            )

            if isinstance(message, types.Message):
                message.bot.send_message(
                    message.chat.id, ban_message, parse_mode="HTML"
                )
            elif isinstance(message, types.CallbackQuery):
                message.bot.answer_callback_query(
                    message.id, "🚫 Доступ заблокирован", show_alert=True
                )
                message.bot.send_message(
                    message.message.chat.id, ban_message, parse_mode="HTML"
                )

            logger.warning(f"🚫 Banned user {user_id} tried to access bot")
            raise Exception("User is banned")

    def post_process(self, message, data, exception):
        """Processing after the handler is executed."""
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
