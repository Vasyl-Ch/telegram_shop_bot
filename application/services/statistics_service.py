"""
Statistics Service is a service for calculating statistics.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from infrastructure.repositories.order_repository import OrderRepository
from domain.enums.order_status import OrderStatus
from domain.enums.payment_method import PaymentMethod

logger = logging.getLogger(__name__)


class StatisticsService:
    """
A service for calculating order statistics.    """

    def __init__(self, order_repository: OrderRepository):
        """
        Args:
            order_repository: Order Repository
        """
        self.order_repo = order_repository
        logger.info("✅ StatisticsService initialized")

    def get_daily_statistics(self, date: datetime = None) -> Dict[str, Any]:
        """
        Gets daily stats.

        Args:
            date: Date for statistics (default is yesterday)

        Returns:
            Dict: Statistics with has_changes flag
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        all_orders = self.order_repo.get_all()

        daily_orders = [
            o for o in all_orders if start_of_day <= o.created_at <= end_of_day
        ]

        if not daily_orders:
            return {
                "has_changes": False,
                "date": date.strftime("%d.%m.%Y"),
                "message": "За этот день не было заказов.",
            }

        new_orders = len(daily_orders)
        completed_orders = len(
            [o for o in daily_orders if o.status == OrderStatus.DELIVERED]
        )
        cancelled_orders = len(
            [o for o in daily_orders if o.status == OrderStatus.CANCELLED]
        )
        pending_orders = len([o for o in daily_orders if not o.is_final()])

        paid_orders = [o for o in daily_orders if o.is_paid()]
        online_payments = [
            o for o in paid_orders if o.payment_method == PaymentMethod.STRIPE
        ]
        cash_payments = [
            o for o in paid_orders if o.payment_method == PaymentMethod.CASH
        ]

        total_revenue = sum(
            o.total_amount for o in daily_orders if o.status == OrderStatus.DELIVERED
        )
        online_revenue = sum(
            o.total_amount for o in online_payments if o.status == OrderStatus.DELIVERED
        )

        status_changes = [
            o
            for o in all_orders
            if start_of_day <= o.updated_at <= end_of_day
            and o.created_at < start_of_day
        ]

        return {
            "has_changes": True,
            "date": date.strftime("%d.%m.%Y"),
            "new_orders": new_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": cancelled_orders,
            "pending_orders": pending_orders,
            "total_revenue": float(total_revenue),
            "online_payments_count": len(online_payments),
            "cash_payments_count": len(cash_payments),
            "online_revenue": float(online_revenue),
            "status_changes": len(status_changes),
        }

    def format_daily_statistics(self, stats: Dict[str, Any]) -> str:
        """
        Formats the statistics to be sent.

        Args:
            stats: Dictionary with statistics

        Returns:
            str: Formatted message
        """
        if not stats.get("has_changes"):
            return None

        message = (
            f"📊 <b>Статистика за {stats['date']}</b>\n\n"
            f"📦 <b>Заказы:</b>\n"
            f"• Новых: {stats['new_orders']}\n"
            f"• Выполнено: {stats['completed_orders']}\n"
            f"• Отменено: {stats['cancelled_orders']}\n"
            f"• В обработке: {stats['pending_orders']}\n\n"
            f"💳 <b>Оплаты:</b>\n"
            f"• Онлайн: {stats['online_payments_count']} "
            f"({stats['online_revenue']:.2f}₴)\n"
            f"• Наличные: {stats['cash_payments_count']}\n\n"
            f"💰 <b>Выручка: {stats['total_revenue']:.2f}₴</b>\n"
        )

        if stats["status_changes"] > 0:
            message += f"\n🔄 Изменений статусов: {stats['status_changes']}"

        return message
