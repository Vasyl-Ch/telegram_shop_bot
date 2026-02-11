"""
Stripe payment provider (Checkout Session without webhook).

Features:
- Uses Stripe Checkout Session
- Does not require a webhook URL
- Status is checked through polling
- Production-ready
"""

import stripe
from typing import Dict, Any, Optional
import logging

from infrastructure.payments.payment_provider import (
    PaymentProvider,
    PaymentProviderError,
)
from domain.entities.order import Order
from config.settings import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key


class StripeProvider(PaymentProvider):
    """
    Stripe Checkout Session implementation.

    Why Checkout Session:
    - PCI DSS compliance out of the box
    - Ready-made UI for payment
    - Automatic 3D Secure processing
    - Built-in error handling
    - Does not require front-end development
    """

    def __init__(self):
        """Provider initialization."""
        self.success_url = f"https://t.me/{settings.bot_username}?start=payment_success"
        self.cancel_url = (
            f"https://t.me/{settings.bot_username}?start=payment_cancelled"
        )

        logger.info("✅ StripeProvider initialized (polling mode)")

    async def create_payment(self, order: Order) -> Dict[str, Any]:
        """
        Creates a Stripe Checkout Session.

        Features:
        - One-time session (expires_at after 4 hours)
        - All order data in metadata for recovery
        - Line items from the order

        Args:
            order: Order for payment

        Returns:
            Dict with payment_url and session_id

        Raises:
            PaymentProviderError: On Stripe API error
        """
        try:
            line_items = []
            for item in order.items:
                line_items.append(
                    {
                        "price_data": {
                            "currency": "uah",
                            "unit_amount": int(item.price * 100),
                            "product_data": {
                                "name": item.name,
                                "description": f"Quantity: {item.quantity}",
                            },
                        },
                        "quantity": item.quantity,
                    }
                )

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=line_items,
                mode="payment",
                metadata={
                    "order_id": str(order.order_id),
                    "chat_id": str(order.chat_id),
                    "phone": order.phone,
                    "address": order.address,
                    "total_amount": str(order.total_amount),
                    "created_at": order.created_at.isoformat(),
                },
                client_reference_id=f"order_{order.order_id}",
                success_url=self.success_url,
                cancel_url=self.cancel_url,
                expires_at=int(order.created_at.timestamp() + 14400),
                payment_intent_data={
                    "description": f"Order #{order.order_id} - {order.phone}",
                    "metadata": {
                        "order_id": str(order.order_id),
                        "chat_id": str(order.chat_id),
                    },
                },
                billing_address_collection="auto",
                phone_number_collection={"enabled": True},
                # Automatic taxes (if configured in Stripe)
                # automatic_tax={'enabled': True},
                # Support promo codes (if needed)
                # allow_promotion_codes=True,
            )

            logger.info(
                f"✅ Stripe Checkout Session created: {session.id} "
                f"for order #{order.order_id}"
            )

            return {
                "payment_url": session.url,
                "payment_id": session.id,
                "status": session.status,
                "metadata": {
                    "session_id": session.id,
                    "payment_intent": session.payment_intent,
                    "expires_at": session.expires_at,
                },
            }

        except stripe.error.CardError as e:
            logger.error(f"❌ Stripe CardError: {e}")
            raise PaymentProviderError(f"Card error: {e.user_message}") from e

        except stripe.error.InvalidRequestError as e:
            logger.error(f"❌ Stripe InvalidRequestError: {e}")
            raise PaymentProviderError(f"Invalid request: {str(e)}") from e

        except stripe.error.AuthenticationError as e:
            logger.error(f"❌ Stripe AuthenticationError: {e}")
            raise PaymentProviderError("Payment system authentication error") from e

        except stripe.error.APIConnectionError as e:
            logger.error(f"❌ Stripe APIConnectionError: {e}")
            raise PaymentProviderError("Payment system connection error") from e

        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error: {e}")
            raise PaymentProviderError(f"Stripe error: {str(e)}") from e

        except Exception as e:
            logger.error(f"❌ Unexpected error creating payment: {e}", exc_info=True)
            raise PaymentProviderError(f"Payment creation failed: {str(e)}") from e

    async def verify_payment(self, payment_id: str) -> bool:
        """
        Checks the status of the Checkout Session.

        This is the main method for polling - called regularly
        background worker.

        Args:
            payment_id: ID Stripe Checkout Session

        Returns:
            bool: True if paid
        """
        try:
            session = stripe.checkout.Session.retrieve(
                payment_id, expand=["payment_intent"]
            )

            is_paid = session.payment_status == "paid"

            if is_paid:
                logger.info(f"✅ Payment verified: {payment_id}")

            return is_paid

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error verifying payment {payment_id}: {e}")
            return False

    async def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Gets full information about the Checkout Session.

        It is used when processing a successful payment.

        Args:
            payment_id: ID Checkout Session

        Returns:
            Optional[Dict]: Session Details or None
        """
        try:
            session = stripe.checkout.Session.retrieve(
                payment_id, expand=["payment_intent", "customer"]
            )

            return {
                "session_id": session.id,
                "payment_status": session.payment_status,
                "payment_intent_id": (
                    session.payment_intent.id if session.payment_intent else None
                ),
                "amount_total": session.amount_total,
                "amount_received": (
                    session.payment_intent.amount_received
                    if session.payment_intent
                    else None
                ),
                "currency": session.currency,
                "customer_email": (
                    session.customer_details.email if session.customer_details else None
                ),
                "customer_phone": (
                    session.customer_details.phone if session.customer_details else None
                ),
                "metadata": session.metadata,
                "created": session.created,
                "expires_at": session.expires_at,
            }

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error retrieving session {payment_id}: {e}")
            return None

    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Cancels an incomplete payment.

        Note: Stripe Checkout Sessions cannot be explicitly canceled,
        but it is possible to cancel the Payment Intent if it has not yet been confirmed.

        Args:
            payment_id: ID Checkout Session

        Returns:
            bool: True if the cancellation is successful
        """
        try:
            session = stripe.checkout.Session.retrieve(payment_id)

            if session.payment_intent:
                payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)

                if payment_intent.status in [
                    "requires_payment_method",
                    "requires_confirmation",
                    "requires_action",
                ]:
                    stripe.PaymentIntent.cancel(session.payment_intent)
                    logger.info(
                        f"✅ Cancelled Payment Intent: {session.payment_intent}"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ Cannot cancel Payment Intent in status: "
                        f"{payment_intent.status}"
                    )
                    return False

            return False

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error cancelling payment {payment_id}: {e}")
            return False

    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "Stripe"

    async def refund_payment(
        self, payment_intent_id: str, amount: Optional[int] = None
    ) -> bool:
        """
        Refund (additional method).

        Args:
            payment_intent_id: ID Payment Intent
            amount: Refund amount in cents (None = full refund)

        Returns:
            bool: True if the refund is successful
        """
        try:
            refund_params = {"payment_intent": payment_intent_id}
            if amount:
                refund_params["amount"] = amount

            refund = stripe.Refund.create(**refund_params)

            logger.info(
                f"✅ Refund created: {refund.id} "
                f"for Payment Intent: {payment_intent_id}"
            )
            return refund.status in ["succeeded", "pending"]

        except stripe.error.StripeError as e:
            logger.error(f"❌ Error creating refund: {e}")
            return False
