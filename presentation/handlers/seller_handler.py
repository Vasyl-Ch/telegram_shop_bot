"""
Seller panel handlers.

Access is only for SELLER_CHAT_ID.
"""

import logging
import telebot
from telebot import types

from application.services.order_service import OrderService
from infrastructure.repositories.order_repository import OrderRepository
from infrastructure.repositories.catalog_repository import CatalogRepository
from infrastructure.repositories.user_limit_repository import UserLimitRepository
from domain.enums.order_status import OrderStatus
from presentation.keyboards.inline_keyboards import get_seller_order_keyboard
from presentation.keyboards.main_keyboards import get_seller_main_keyboard
from utils.formatters import (
    format_order_for_seller,
    format_order_status_update,
)
from utils.helpers import get_customer_name

logger = logging.getLogger(__name__)


def register_seller_handlers(
    bot: telebot.TeleBot,
    order_service: OrderService,
    order_repo: OrderRepository,
    seller_chat_id: str,
    catalog_repo: CatalogRepository,
    user_limit_repo: UserLimitRepository,
) -> None:
    """
    Registers seller panel handlers.

    Args:
        bot: Bot instance
        order_service: Order Service
        order_repo: Order Repository
        seller_chat_id: Merchant Chat ID
        catalog_repo: Directory Repository
        user_limit_repo:
    """

    def is_seller(chat_id: int) -> bool:
        """Verifies that the user is a seller."""
        return str(chat_id) == str(seller_chat_id)

    # ──────────────────────────────────────────────
    # command /seller
    # ──────────────────────────────────────────────

    @bot.message_handler(commands=["seller"])
    def handle_seller_panel(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            bot.send_message(message.chat.id, "⛔ Доступ запрещён.")
            return

        bot.send_message(
            message.chat.id,
            "👨‍💼 <b>Панель продавца</b>",
            parse_mode="HTML",
            reply_markup=get_seller_main_keyboard(),
        )

    # ──────────────────────────────────────────────
    # Active Orders
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "📋 Активные заказы")
    def handle_active_orders(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        active = [
            o for o in order_repo.get_all()
            if not o.is_final()
        ]

        if not active:
            bot.send_message(message.chat.id, "Нет активных заказов.")
            return

        for order in active:
            customer_name = get_customer_name(bot, order.chat_id)
            text = format_order_for_seller(order, customer_name)
            stage = "confirmed" if order.status == OrderStatus.CONFIRMED else "new"
            bot.send_message(
                message.chat.id,
                text,
                parse_mode="HTML",
                reply_markup=get_seller_order_keyboard(order, stage=stage),
            )

    # ──────────────────────────────────────────────
    # Completed orders
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "✅ Выполненные")
    def handle_delivered_orders(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        delivered = order_repo.get_by_status(OrderStatus.DELIVERED)
        if not delivered:
            bot.send_message(message.chat.id, "Нет выполненных заказов.")
            return

        lines = [f"✅ <b>Выполненные заказы: {len(delivered)}</b>\n"]
        for order in delivered[-10:]:
            lines.append(
                f"#{order.order_id} | "
                f"{order.total_amount}₴ | "
                f"{order.created_at.strftime('%d.%m %H:%M')}"
            )

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
        )

        # ──────────────────────────────────────────────
        # Menu "Orders"
        # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "🗂 Заказы")
    def handle_orders_menu(message: types.Message) -> None:
        """Shows the order management menu."""
        if not is_seller(message.chat.id):
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.row(
            types.KeyboardButton("📋 История выполненных"),
            types.KeyboardButton("⏳ История незавершённых"),
        )
        markup.row(
            types.KeyboardButton("⬅️ Назад в главное меню"),
        )

        bot.send_message(
            message.chat.id,
            "🗂 <b>Управление заказами</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=markup,
        )

    @bot.message_handler(func=lambda m: m.text == "📋 История выполненных")
    def handle_completed_orders_history(message: types.Message) -> None:
        """Detailed history of completed orders."""
        if not is_seller(message.chat.id):
            return

        delivered = order_repo.get_by_status(OrderStatus.DELIVERED)
        if not delivered:
            bot.send_message(message.chat.id, "Нет выполненных заказов.")
            return

        for order in sorted(delivered, key=lambda o: o.created_at, reverse=True)[:20]:
            customer_name = get_customer_name(bot, order.chat_id)
            text = format_order_for_seller(order, customer_name)
            bot.send_message(message.chat.id, text, parse_mode="HTML")

        bot.send_message(
            message.chat.id,
            f"✅ Показано {min(len(delivered), 20)} из {len(delivered)} выполненных заказов",
        )

    @bot.message_handler(func=lambda m: m.text == "⏳ История незавершённых")
    def handle_pending_orders_history(message: types.Message) -> None:
        """Detailed history of unfinished orders."""
        if not is_seller(message.chat.id):
            return

        all_orders = order_repo.get_all()
        pending = [o for o in all_orders if not o.is_final()]

        if not pending:
            bot.send_message(message.chat.id, "Нет незавершённых заказов.")
            return

        for order in sorted(pending, key=lambda o: o.created_at, reverse=True):
            customer_name = get_customer_name(bot, order.chat_id)
            text = format_order_for_seller(order, customer_name)

            stage = "confirmed" if order.status == OrderStatus.CONFIRMED else "new"
            bot.send_message(
                message.chat.id,
                text,
                parse_mode="HTML",
                reply_markup=get_seller_order_keyboard(order, stage=stage),
            )

        bot.send_message(
            message.chat.id,
            f"⏳ Всего незавершённых заказов: {len(pending)}",
        )

    # ──────────────────────────────────────────────
    # Payments menu
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "💳 Платежи")
    def handle_payments_menu(message: types.Message) -> None:
        """Shows the payment management menu."""
        if not is_seller(message.chat.id):
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.row(
            types.KeyboardButton("💳 История онлайн-оплат"),
        )
        markup.row(
            types.KeyboardButton("⬅️ Назад в главное меню"),
        )

        bot.send_message(
            message.chat.id,
            "💳 <b>Управление платежами</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=markup,
        )

    @bot.message_handler(func=lambda m: m.text == "💳 История онлайн-оплат")
    def handle_online_payments_history(message: types.Message) -> None:
        """Online payment history with Stripe."""
        if not is_seller(message.chat.id):
            return

        from domain.enums.payment_method import PaymentMethod

        all_orders = order_repo.get_all()
        stripe_orders = [o for o in all_orders if o.is_stripe_paid()]

        if not stripe_orders:
            bot.send_message(message.chat.id, "Нет онлайн-оплат.")
            return

        lines = [f"💳 <b>История онлайн-оплат: {len(stripe_orders)}</b>\n"]

        total_amount = sum(o.total_amount for o in stripe_orders)

        for order in sorted(stripe_orders, key=lambda o: o.created_at, reverse=True)[
            :15
        ]:
            payment_date = order.updated_at.strftime("%d.%m.%Y %H:%M")
            lines.append(
                f"#{order.order_id} | "
                f"{order.total_amount}₴ | "
                f"{payment_date} | "
                f"{order.status.display_name}"
            )

        lines.append(f"\n💰 <b>Общая сумма онлайн-оплат: {total_amount:.2f}₴</b>")

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
        )

    @bot.message_handler(func=lambda m: m.text == "⬅️ Назад в главное меню")
    def handle_back_to_seller_menu(message: types.Message) -> None:
        """Return to the seller's main menu."""
        if not is_seller(message.chat.id):
            return

        bot.send_message(
            message.chat.id,
            "👨‍💼 <b>Панель продавца</b>",
            parse_mode="HTML",
            reply_markup=get_seller_main_keyboard(),
        )

    # ──────────────────────────────────────────────
    # User management
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "👥 Управление пользователями")
    def handle_users_menu(message: types.Message) -> None:
        """Shows the user management menu."""
        if not is_seller(message.chat.id):
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.row(
            types.KeyboardButton("🚫 Добавить в бан"),
            types.KeyboardButton("✅ Снять бан"),
        )
        markup.row(
            types.KeyboardButton("📋 Список забаненных"),
            types.KeyboardButton("🔓 Снять лимит"),
        )
        markup.row(
            types.KeyboardButton("⬅️ Назад в главное меню"),
        )

        bot.send_message(
            message.chat.id,
            "👥 <b>Управление пользователями</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=markup,
        )

    @bot.message_handler(func=lambda m: m.text == "🚫 Добавить в бан")
    def handle_ban_user_start(message: types.Message) -> None:
        """Start of the user ban process."""
        if not is_seller(message.chat.id):
            return

        bot.send_message(
            message.chat.id,
            "🚫 <b>Бан пользователя</b>\n\n"
            "Введите ID пользователя (chat_id) которого нужно забанить:\n"
            "Например: 123456789",
            parse_mode="HTML",
        )
        bot.register_next_step_handler(message, _process_ban_user_id)

    def _process_ban_user_id(message: types.Message) -> None:
        """Handles ID input for banning."""
        if not is_seller(message.chat.id):
            return

        try:
            user_id = int(message.text.strip())

            if str(user_id) == seller_chat_id:
                bot.send_message(
                    message.chat.id,
                    "❌ Нельзя забанить продавца!",
                )
                return

            if not hasattr(bot, "_temp_ban_data"):
                bot._temp_ban_data = {}
            bot._temp_ban_data[message.chat.id] = user_id

            bot.send_message(
                message.chat.id,
                f"Введите причину бана для пользователя {user_id}:",
            )
            bot.register_next_step_handler(message, _process_ban_reason)

        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Некорректный ID. Введите число.",
            )

    def _process_ban_reason(message: types.Message) -> None:
        """Handles the entry of the ban reason."""
        if not is_seller(message.chat.id):
            return

        reason = message.text.strip()
        user_id = bot._temp_ban_data.get(message.chat.id)

        if not user_id:
            bot.send_message(message.chat.id, "❌ Ошибка: ID не найден.")
            return

        try:
            limit = user_limit_repo.get_or_create(user_id)
            limit.ban_user(reason)
            user_limit_repo.update(limit)

            del bot._temp_ban_data[message.chat.id]

            bot.send_message(
                message.chat.id,
                f"✅ Пользователь {user_id} забанен.\n" f"Причина: {reason}",
                reply_markup=get_seller_main_keyboard(),
            )

            try:
                bot.send_message(
                    user_id,
                    f"🚫 <b>Ваш доступ к боту заблокирован</b>\n\n"
                    f"Причина: {reason}\n\n"
                    "Для разблокировки свяжитесь с администратором.",
                    parse_mode="HTML",
                )
            except Exception:
                logger.warning(f"Could not notify user {user_id} about ban")

        except Exception as e:
            logger.error(f"Error banning user: {e}")
            bot.send_message(
                message.chat.id,
                f"❌ Ошибка при бане пользователя: {e}",
            )

    @bot.message_handler(func=lambda m: m.text == "✅ Снять бан")
    def handle_unban_user_start(message: types.Message) -> None:
        """The start of the process of removing the ban."""
        if not is_seller(message.chat.id):
            return

        bot.send_message(
            message.chat.id,
            "✅ <b>Снятие бана</b>\n\n"
            "Введите ID пользователя (chat_id) для снятия бана:\n"
            "Например: 123456789",
            parse_mode="HTML",
        )
        bot.register_next_step_handler(message, _process_unban_user)

    def _process_unban_user(message: types.Message) -> None:
        """Handles the removal of the ban."""
        if not is_seller(message.chat.id):
            return

        try:
            user_id = int(message.text.strip())

            limit = user_limit_repo.get(user_id)
            if not limit or not limit.is_banned:
                bot.send_message(
                    message.chat.id,
                    f"ℹ️ Пользователь {user_id} не забанен.",
                )
                return

            limit.unban_user()
            user_limit_repo.update(limit)

            bot.send_message(
                message.chat.id,
                f"✅ Бан снят с пользователя {user_id}",
                reply_markup=get_seller_main_keyboard(),
            )

            try:
                bot.send_message(
                    user_id,
                    "✅ <b>Ваш доступ к боту восстановлен</b>\n\n"
                    "Добро пожаловать обратно!",
                    parse_mode="HTML",
                )
            except Exception:
                logger.warning(f"Could not notify user {user_id} about unban")

        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Некорректный ID. Введите число.",
            )
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            bot.send_message(
                message.chat.id,
                f"❌ Ошибка при снятии бана: {e}",
            )

    @bot.message_handler(func=lambda m: m.text == "📋 Список забаненных")
    def handle_banned_list(message: types.Message) -> None:
        """Shows a list of banned users."""
        if not is_seller(message.chat.id):
            return

        banned = user_limit_repo.get_all_banned()

        if not banned:
            bot.send_message(message.chat.id, "✅ Нет забаненных пользователей.")
            return

        lines = [f"🚫 <b>Забаненные пользователи: {len(banned)}</b>\n"]

        for limit in banned:
            ban_date = (
                limit.banned_at.strftime("%d.%m.%Y %H:%M")
                if limit.banned_at
                else "неизвестно"
            )
            lines.append(
                f"• ID: {limit.chat_id}\n"
                f"  Причина: {limit.ban_reason or 'не указана'}\n"
                f"  Дата: {ban_date}\n"
            )

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
        )

    @bot.message_handler(func=lambda m: m.text == "🔓 Снять лимит")
    def handle_remove_limit_start(message: types.Message) -> None:
        """Beginning of the process of removing the limit."""
        if not is_seller(message.chat.id):
            return

        bot.send_message(
            message.chat.id,
            "🔓 <b>Снятие лимита</b>\n\n"
            "Введите ID пользователя (chat_id) для снятия лимита:\n"
            "Например: 123456789\n\n"
            "Это снимет как автоматический лимит за превышение, "
            "так и любые установленные ограничения.",
            parse_mode="HTML",
        )
        bot.register_next_step_handler(message, _process_remove_limit)

    def _process_remove_limit(message: types.Message) -> None:
        """Handles limit removals."""
        if not is_seller(message.chat.id):
            return

        try:
            user_id = int(message.text.strip())

            limit = user_limit_repo.get(user_id)
            if not limit:
                bot.send_message(
                    message.chat.id,
                    f"ℹ️ У пользователя {user_id} нет установленных лимитов.",
                )
                return

            limit.remove_custom_limit()
            user_limit_repo.update(limit)

            bot.send_message(
                message.chat.id,
                f"✅ Лимиты сняты с пользователя {user_id}",
                reply_markup=get_seller_main_keyboard(),
            )

            try:
                bot.send_message(
                    user_id,
                    "✅ <b>Ваши лимиты сняты</b>\n\n"
                    "Вы можете продолжить использование бота без ограничений.",
                    parse_mode="HTML",
                )
            except Exception:
                logger.warning(f"Could not notify user {user_id} about limit removal")

        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Некорректный ID. Введите число.",
            )
        except Exception as e:
            logger.error(f"Error removing limit: {e}")
            bot.send_message(
                message.chat.id,
                f"❌ Ошибка при снятии лимита: {e}",
            )

    # ──────────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "📊 Статистика")
    def handle_statistics(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        all_orders = order_repo.get_all()
        total = len(all_orders)
        delivered = len(order_repo.get_by_status(OrderStatus.DELIVERED))
        cancelled = len(order_repo.get_by_status(OrderStatus.CANCELLED))
        pending = len([o for o in all_orders if not o.is_final()])

        total_revenue = sum(
            o.total_amount
            for o in order_repo.get_by_status(OrderStatus.DELIVERED)
        )

        text = (
            f"📊 <b>Статистика магазина</b>\n\n"
            f"📦 Всего заказов: {total}\n"
            f"✅ Выполнено: {delivered}\n"
            f"❌ Отменено: {cancelled}\n"
            f"⏳ В обработке: {pending}\n\n"
            f"💰 Выручка: {total_revenue:.2f}₴"
        )

        bot.send_message(message.chat.id, text, parse_mode="HTML")

    # ──────────────────────────────────────────────
    # Little in stock
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "⚠️ Мало на складе")
    def handle_low_stock(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        low_stock = catalog_repo.get_low_stock_products(threshold=5)
        if not low_stock:
            bot.send_message(message.chat.id, "✅ Все товары в норме!")
            return

        lines = [f"⚠️ <b>Товары с низким остатком:</b>\n"]
        for product in low_stock:
            lines.append(f"• {product.name} — {product.stock} шт.")

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
        )

    # ──────────────────────────────────────────────
    # Updating the catalog by the seller
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "🔄 Обновить каталог")
    def handle_seller_reload(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        try:
            catalog_repo.reload()
            bot.send_message(message.chat.id, "✅ Каталог обновлён!")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

    # ──────────────────────────────────────────────
    # Order confirmation
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("seller_confirm:")
    )
    def handle_confirm_order(call: types.CallbackQuery) -> None:
        if not is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа.")
            return

        order_id = int(call.data.split(":")[1])

        try:
            order = order_service.confirm_order(order_id)
            customer_name = get_customer_name(bot, order.chat_id)

            bot.edit_message_text(
                text=format_order_for_seller(order, customer_name),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=get_seller_order_keyboard(order, stage="confirmed"),
            )

            bot.answer_callback_query(call.id, "✅ Заказ подтверждён!")

            bot.send_message(
                order.chat_id,
                format_order_status_update(order),
                parse_mode="HTML",
            )

        except Exception as e:
            logger.error(f"Confirm order error: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка подтверждения.")

    # ──────────────────────────────────────────────
    # Delivered
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("seller_deliver:")
    )
    def handle_deliver_order(call: types.CallbackQuery) -> None:
        if not is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа.")
            return

        order_id = int(call.data.split(":")[1])

        try:
            order = order_service.mark_as_delivered(order_id)
            customer_name = get_customer_name(bot, order.chat_id)

            bot.edit_message_text(
                text=(
                    f"🚚 <b>ЗАКАЗ #{order_id} ДОСТАВЛЕН</b>\n\n"
                    + format_order_for_seller(order, customer_name)
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=None,
            )

            bot.answer_callback_query(call.id, "🚚 Заказ доставлен! Товары списаны.")

            bot.send_message(
                order.chat_id,
                format_order_status_update(order),
                parse_mode="HTML",
            )

        except Exception as e:
            logger.error(f"Deliver order error: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка.")

    # ──────────────────────────────────────────────
    # Cancellation by the seller
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("seller_cancel:")
    )
    def handle_seller_cancel(call: types.CallbackQuery) -> None:
        if not is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа.")
            return

        order_id = int(call.data.split(":")[1])

        try:
            order = order_service.cancel_order(
                order_id, reason="Отменён менеджером"
            )
            customer_name = get_customer_name(bot, order.chat_id)

            bot.edit_message_text(
                text=(
                    f"❌ <b>ЗАКАЗ #{order_id} ОТМЕНЁН</b>\n\n"
                    + format_order_for_seller(order, customer_name)
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=None,
            )

            bot.answer_callback_query(call.id, "❌ Заказ отменён.")

            bot.send_message(
                order.chat_id,
                format_order_status_update(order),
                parse_mode="HTML",
            )

        except Exception as e:
            logger.error(f"Seller cancel error: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка отмены.")
