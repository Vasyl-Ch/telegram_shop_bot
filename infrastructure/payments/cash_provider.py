"""
Cash on Delivery (COD) payment provider.

Features:
- Does not create real payments
- "Null object" pattern
- Conforms to the PaymentProvider interface
- Payment is confirmed manually by the manager
"""

from typing import Dict, Any, Optional
import logging

from infrastructure.payments.payment_provider import PaymentProvider
from domain.entities.order import Order

logger = logging.getLogger(__name__)


class CashProvider(PaymentProvider):
    """
    Cash on Delivery provider.

Features:
    - Does not create external payments
    - Payment is considered "pending" until confirmed by the manager
    - Does not require webhook or polling
    - Confirmation of the manager's button via Telegram
    """

    async def create_payment(self, order: Order) -> Dict[str, Any]:
        """
        "Creates" a COD payment (in fact, just logs).

        Args:
            order: Order

        Returns:
            Dict with minimal data (no payment_url)
        """
        logger.info(
            f"💵 COD payment initiated for order #{order.order_id}, "
            f"amount: {order.total_amount}₴"
        )

        payment_id = f"cash_{order.order_id}_{int(order.created_at.timestamp())}"

        return {
            "payment_url": None,
            "payment_id": payment_id,
            "status": "pending_confirmation",
            "metadata": {
                "method": "cash_on_delivery",
                "requires_manager_confirmation": True,
                "amount": float(order.total_amount),
            },
        }

    async def verify_payment(self, payment_id: str) -> bool:
        """
        COD payments cannot be verified automatically.

        Manual confirmation of the manager is required upon delivery.

        Args:
            payment_id: "payment" ID

        Returns:
            bool: Always False (manual confirmation needed)
        """
        logger.debug(f"💵 COD payment verification requested for {payment_id}")
        return False

    async def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns the minimum COD payment information.

        Args:
            payment_id: "payment" ID

        Returns:
            Optional[Dict]: Details
        """

        try:
            parts = payment_id.split("_")
            if len(parts) >= 3 and parts[0] == "cash":
                return {
                    "payment_id": payment_id,
                    "method": "cash_on_delivery",
                    "status": "pending_confirmation",
                    "order_id": int(parts[1]),
                    "created": int(parts[2]),
                }
        except Exception as e:
            logger.error(f"Error parsing COD payment_id {payment_id}: {e}")

        return None

    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Canceling COD is just logging.

        Args:
            payment_id: "payment" ID

        Returns:
            bool: Always True (no external payment to cancel)
        """
        logger.info(f"❌ COD payment cancelled: {payment_id}")
        return True

    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "Cash on Delivery"
