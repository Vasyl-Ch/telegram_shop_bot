"""
Enum для способов оплаты.

Применение SOLID:
- Single Responsibility: только определение способов оплаты
- Open/Closed: легко добавить новые методы без изменения кода

Почему Enum:
- Предотвращает опечатки в строках
- Автокомплит в IDE
- Централизованное управление способами оплаты
- Type safety
"""

from enum import Enum


class PaymentMethod(str, Enum):
    """
    Способы оплаты в системе.

    Наследуется от str для совместимости с JSON/DB сериализацией.
    """

    STRIPE = "stripe"
    """Онлайн-оплата через Stripe (картой)."""

    CASH = "cash"
    """Оплата наличными курьеру при получении."""

    # Готово к расширению:
    # PAYPAL = "paypal"
    # BANK_TRANSFER = "bank_transfer"
    # CRYPTO = "crypto"

    def __str__(self) -> str:
        """String representation."""
        return self.value

    @property
    def display_name(self) -> str:
        """
        Человекочитаемое название для UI.

        Returns:
            str: Название с emoji для Telegram
        """
        names = {
            self.STRIPE: "💳 Онлайн-оплата картой",
            self.CASH: "💵 Наличными курьеру",
        }
        return names.get(self, self.value)

    @property
    def requires_online_payment(self) -> bool:
        """
        Требуется ли онлайн-оплата.

        Returns:
            bool: True если нужен payment gateway
        """
        return self == PaymentMethod.STRIPE

    @property
    def description(self) -> str:
        """
        Описание способа оплаты для пользователя.

        Returns:
            str: Детальное описание
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
