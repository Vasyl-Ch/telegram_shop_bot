"""
Абстрактный интерфейс платежного провайдера.

Применение SOLID:
- Interface Segregation: минимальный набор методов
- Dependency Inversion: зависимость от абстракции
- Open/Closed: закрыт для изменений, открыт для расширения

Паттерн Strategy:
- Разные способы оплаты реализуют один интерфейс
- Легко добавлять новые провайдеры
- Взаимозаменяемость
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from domain.entities.order import Order


class PaymentProvider(ABC):
    """
    Абстрактный интерфейс платежного провайдера.

    Любой новый провайдер (PayPal, Crypto и т.д.) должен
    реализовать этот интерфейс.
    """

    @abstractmethod
    async def create_payment(self, order: Order) -> Dict[str, Any]:
        """
        Создает платеж для заказа.

        Args:
            order: Заказ для оплаты

        Returns:
            Dict с данными платежа:
            {
                'payment_url': Optional[str],  # URL для оплаты (если есть)
                'payment_id': str,             # ID платежа в системе провайдера
                'status': str,                 # Статус платежа
                'metadata': dict               # Дополнительные данные
            }

        Raises:
            PaymentProviderError: при ошибке создания платежа
        """
        pass

    @abstractmethod
    async def verify_payment(self, payment_id: str) -> bool:
        """
        Проверяет статус платежа.

        Args:
            payment_id: ID платежа в системе провайдера

        Returns:
            bool: True если платеж успешен, False иначе
        """
        pass

    @abstractmethod
    async def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает детальную информацию о платеже.

        Args:
            payment_id: ID платежа

        Returns:
            Optional[Dict]: Детали платежа или None если не найден
        """
        pass

    @abstractmethod
    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Отменяет платеж (если возможно).

        Args:
            payment_id: ID платежа

        Returns:
            bool: True если отмена успешна
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Название провайдера для логирования.

        Returns:
            str: Название провайдера
        """
        pass


class PaymentProviderError(Exception):
    """
    Исключение для ошибок платежного провайдера.

    Используется для абстрагирования от конкретных ошибок
    разных провайдеров (Stripe, PayPal и т.д.).
    """
    pass