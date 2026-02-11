"""
Abstract payment provider interface.

Applications of SOLID:
- Interface Segregation: A minimum set of methods
- Dependency Inversion: Dependency on Abstraction
- Open/Closed: Closed for changes, open for expansion

Strategy Pattern:
- Different payment methods implement the same interface
- Easy to add new providers
- Interchangeability
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from domain.entities.order import Order


class PaymentProvider(ABC):
    """
    Abstract payment provider interface.

    Any new provider (PayPal, Crypto, etc.) should
    implement this interface.
    """

    @abstractmethod
    async def create_payment(self, order: Order) -> Dict[str, Any]:
        """
        Creates a payment for the order.

        Args:
            order: Order for payment

        Returns:
            Dict with payment details:
            {
                'payment_url': Optional[str], # URL for payment (if any)
                'payment_id': str, # payment ID in the provider's system
                'status': str, # Payment status
                'metadata': dict # Additional data
            }

        Raises:
            PaymentProviderError: On payment creation error
        """
        pass

    @abstractmethod
    async def verify_payment(self, payment_id: str) -> bool:
        """
        Checks the status of the payment.

        Args:
            payment_id: Payment ID in the provider's system

        Returns:
            bool: True if the payment is successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Receives detailed information about the payment.

        Args:
            payment_id: Payment ID

        Returns:
            Optional[Dict]: Payment details or None if not found
        """
        pass

    @abstractmethod
    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Cancels the payment (if possible).

        Args:
            payment_id: Payment ID

        Returns:
            bool: True if the cancellation is successful
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Name of the provider for logging.

        Returns:
            str: Provider name
        """
        pass


class PaymentProviderError(Exception):
    """
    Exception for payment provider errors.

    Used to abstract from specific errors
    different providers (Stripe, PayPal, etc.).
    """

    pass
