"""
Enum for payment methods.

Applications of SOLID:
- Single Responsibility: Only defining payment methods
- Open/Closed: Easily add new methods without changing the code

Why Enum:
- Prevents typos in strings
- Autocomplete in the IDE
- Centralized management of payment methods
- Type safety
"""

from enum import Enum


class PaymentMethod(str, Enum):
    """
    Payment methods in the system.

    Inherits from str for compatibility with JSON/DB serialization.
    """

    STRIPE = "stripe"
    """Online payment via Stripe (by card)."""

    CASH = "cash"
    """Payment in cash to the courier upon receipt."""

    # Ready to Expand:
    # PAYPAL = "paypal"
    # BANK_TRANSFER = "bank_transfer"
    # CRYPTO = "crypto"

    def __str__(self) -> str:
        """String representation."""
        return self.value

    @property
    def display_name(self) -> str:
        """
        Human-readable name for UI.

        Returns:
            str: Name with emoji for Telegram
        """
        names = {
            self.STRIPE: "💳 Онлайн-оплата картой",
            self.CASH: "💵 Наличными курьеру",
        }
        return names.get(self, self.value)

    @property
    def requires_online_payment(self) -> bool:
        """
        Is online payment required?

        Returns:
            bool: True if payment gateway is needed
        """
        return self == PaymentMethod.STRIPE

    @property
    def description(self) -> str:
        """
       A description of the payment method for the user.

        Returns:
            str: Detailed Description
        """
        descriptions = {
            self.STRIPE: (
                "Безопасная оплата банковской картой через Stripe.\n"
                "Принимаем Visa, Mastercard, American Express."
            ),
            self.CASH: (
                "Оплата наличными при получении заказа.\n"
                "Курьер привезет заказ, вы оплачиваете на месте."
            ),
        }
        return descriptions.get(self, "")
