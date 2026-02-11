"""
Payment Poller is a background worker for checking payment statuses.

Architecture:
- Runs in a separate thread
- Checks pending Stripe payments every 60 seconds
- Updates statuses and notifies users
- Graceful shutdown
- Does not lose payments even in case of failures

Applications of SOLID:
- Single Responsibility: Only polling payments
- Dependency Injection: Gets dependencies through the constructor
- Interface Segregation: Uses callbacks for notifications
"""

import asyncio
import logging
from typing import List, Callable, Optional
from datetime import datetime, timedelta
import threading

from domain.entities.order import Order
from infrastructure.payments.stripe_provider import StripeProvider

logger = logging.getLogger(__name__)


class PaymentPoller:
    """
    Polling service to check the status of Stripe payments.

    Why a separate class:
    - Single Responsibility (polling only)
    - Easy to test
    - Can be replaced with Celery/RQ in the future
    - Isolated logic
    """

    def __init__(
        self,
        stripe_provider: StripeProvider,
        order_service,
        payment_service,
        poll_interval: int = 60,
        max_age_hours: int = 24,
    ):
        """
        Initializing the poller.

        Args:
            stripe_provider: Provider Stripe Instance
            get_pending_orders: Function for receiving pending orders
            on_payment_success: Callback on successful payment
            on_payment_failed: Callback in case of unsuccessful payment
            poll_interval: Check Interval (Seconds)
            max_age_hours: Maximum Order Age for Verification
        """
        self.stripe_provider = stripe_provider
        self.order_service = order_service
        self.payment_service = payment_service
        self.poll_interval = poll_interval
        self.max_age_hours = max_age_hours

        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(
            f"✅ PaymentPoller initialized "
            f"(interval: {poll_interval}s, max_age: {max_age_hours}h)"
        )

    def start(self) -> None:
        """
        Runs poller on a background thread.

        Safe to call multiple times - checks _running flag.
        """
        if self._running:
            logger.warning("⚠️ PaymentPoller already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, name="PaymentPoller", daemon=True
        )
        self._thread.start()

        logger.info(f"🚀 PaymentPoller started (interval: {self.poll_interval}s)")

    def stop(self) -> None:
        """
        Stops poller (graceful shutdown).

        Waits for the current iteration to complete (timeout 10 seconds).
        """
        if not self._running:
            logger.info("ℹ️ PaymentPoller already stopped")
            return

        logger.info("🛑 Stopping PaymentPoller...")
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

            if self._thread.is_alive():
                logger.warning("⚠️ PaymentPoller thread did not stop gracefully")
            else:
                logger.info("✅ PaymentPoller stopped")

    def is_running(self) -> bool:
        """
        Checks if poller is running.

        Returns:
            bool: True if working
        """
        return self._running

    def _run_loop(self) -> None:
        """
        The main polling cycle.

        Uses asyncio.run for each iteration,
        to work with the async methods of the provider.
        """
        logger.info("🔄 PaymentPoller loop started")

        while self._running:
            try:
                asyncio.run(self._check_pending_payments())

            except Exception as e:
                logger.error(f"❌ Error in polling loop: {e}", exc_info=True)

            for _ in range(self.poll_interval):
                if not self._running:
                    break
                asyncio.run(asyncio.sleep(1))

        logger.info("🏁 PaymentPoller loop finished")

    async def _check_pending_payments(self) -> None:
        """
        Checks all pending payments.

        Logic:
        1. Gets a list of pending Stripe orders
        2. Filters Too Old
        3. Checks everyone through the Stripe API
        4. Calls callbacks when status changes
        """
        try:
            pending_orders = self.order_service.get_pending_stripe_orders()

            if not pending_orders:
                logger.debug("ℹ️ No pending payments to check")
                return

            logger.info(f"🔍 Checking {len(pending_orders)} pending payment(s)...")

            cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)

            checked_count = 0
            success_count = 0
            failed_count = 0

            for order in pending_orders:
                if order.created_at < cutoff_time:
                    logger.debug(
                        f"⏭️ Skipping old order #{order.order_id} "
                        f"(created {order.created_at})"
                    )
                    continue

                if not order.stripe_session_id:
                    logger.warning(
                        f"⚠️ Order #{order.order_id} has no stripe_session_id"
                    )
                    continue

                result = await self._check_single_order(order)

                if result == "success":
                    success_count += 1
                elif result == "failed":
                    failed_count += 1

                checked_count += 1

                await asyncio.sleep(0.5)

            logger.info(
                f"✅ Checked {checked_count} order(s): "
                f"{success_count} success, {failed_count} failed"
            )

        except Exception as e:
            logger.error(f"❌ Error in _check_pending_payments: {e}", exc_info=True)

    async def _check_single_order(self, order: Order) -> Optional[str]:
        """
        Checks the status of a single order.

        Args:
            order: Order for inspection

        Returns:
            Optional[str]: 'success', 'failed', or None (no change)
        """
        try:
            session_id = order.stripe_session_id

            logger.debug(f"🔍 Checking order #{order.order_id}, session: {session_id}")

            session_details = await self.stripe_provider.get_payment_details(session_id)

            if not session_details:
                logger.warning(
                    f"⚠️ Could not retrieve session for order #{order.order_id}"
                )
                return None

            payment_status = session_details["payment_status"]

            if self._is_session_expired(order, session_details):
                if payment_status != "paid":
                    logger.warning(f"⏰ Session EXPIRED for order #{order.order_id}")
                    try:
                        self.payment_service.handle_payment_failed(order)
                        return "failed"
                    except Exception as e:
                        logger.error(
                            f"Error in on_payment_failed callback: {e}", exc_info=True
                        )
                        return None

            if payment_status == "paid":
                logger.info(f"✅ Payment SUCCESS for order #{order.order_id}")

                try:
                    self.payment_service.handle_payment_success(order, session_details)
                    return "success"
                except Exception as e:
                    logger.error(
                        f"❌ Error in on_payment_success callback: {e}", exc_info=True
                    )
                    return None

            elif payment_status in ["unpaid"]:
                if self._is_session_expired(order, session_details):
                    logger.warning(f"⏰ Payment EXPIRED for order #{order.order_id}")

                    try:
                        self.payment_service.handle_payment_failed(order)
                        return "failed"
                    except Exception as e:
                        logger.error(
                            f"❌ Error in on_payment_failed callback: {e}",
                            exc_info=True,
                        )
                        return None

            elif payment_status == "canceled":
                logger.info(f"❌ Payment CANCELLED for order #{order.order_id}")

                try:
                    self.payment_service.handle_payment_failed(order)
                    return "failed"
                except Exception as e:
                    logger.error(
                        f"❌ Error in on_payment_failed callback: {e}", exc_info=True
                    )
                    return None

            return None

        except Exception as e:
            logger.error(
                f"❌ Error checking order #{order.order_id}: {e}", exc_info=True
            )
            return None

    def _is_session_expired(self, order: Order, session_details: dict) -> bool:
        """
        Checks if the Checkout Session has expired.

        Args:
            order: Order
            session_details: Stripe session details

        Returns:
            bool: True if expired
        """
        expires_at = session_details.get("expires_at")
        if expires_at:
            current_timestamp = int(datetime.now().timestamp())
            return current_timestamp > expires_at

        expiration_time = order.created_at + timedelta(hours=4)
        return datetime.now() > expiration_time
