"""
Product entity (доменная модель товара).

Применение DDD (Domain-Driven Design):
- Товар - это Value Object (идентифицируется по ID)
- Неизменяемый (immutable) для потокобезопасности
- Инкапсулирует бизнес-логику товара
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Product:
    """
    Доменная модель товара.

    Почему frozen=True:
    - Потокобезопасность (immutable)
    - Предотвращает случайное изменение
    - Можно использовать как ключ в dict/set

    Почему Decimal для цены:
    - Точная арифметика для денежных операций
    - Избегаем проблем с float (0.1 + 0.2 != 0.3)
    """

    product_id: int
    """Уникальный идентификатор товара."""

    name: str
    """Название товара."""

    category: str
    """Категория товара."""

    price: Decimal
    """Цена за единицу товара."""

    stock: int
    """Количество на складе."""

    image_url: Optional[str] = None
    """URL изображения товара (опционально)."""

    def __post_init__(self):
        """
        Валидация после инициализации.

        Raises:
            ValueError: Если данные невалидны
        """
        if self.product_id <= 0:
            raise ValueError(f"Invalid product_id: {self.product_id}")

        if not self.name or not self.name.strip():
            raise ValueError("Product name cannot be empty")

        if self.price < 0:
            raise ValueError(f"Price cannot be negative: {self.price}")

        if self.stock < 0:
            raise ValueError(f"Stock cannot be negative: {self.stock}")

    @property
    def is_available(self) -> bool:
        """
        Проверка доступности товара.

        Returns:
            bool: True если товар в наличии
        """
        return self.stock > 0

    @property
    def display_price(self) -> str:
        """
        Форматированная цена для отображения.

        Returns:
            str: Цена с валютой
        """
        return f"{self.price:.2f}₽"

    @property
    def stock_status(self) -> str:
        """
        Статус наличия товара.

        Returns:
            str: Текстовое описание статуса
        """
        if self.stock == 0:
            return "❌ Нет в наличии"
        elif self.stock <= 5:
            return f"⚠️ Осталось {self.stock} шт."
        else:
            return f"✅ В наличии ({self.stock} шт.)"

    def can_fulfill_quantity(self, quantity: int) -> bool:
        """
        Проверяет возможность выполнения заказа на указанное количество.

        Args:
            quantity: Требуемое количество

        Returns:
            bool: True если на складе достаточно товара
        """
        return self.stock >= quantity

    def calculate_total(self, quantity: int) -> Decimal:
        """
        Вычисляет стоимость для указанного количества.

        Args:
            quantity: Количество товара

        Returns:
            Decimal: Общая стоимость
        """
        return self.price * quantity

    @classmethod
    def from_dict(cls, data: dict) -> 'Product':
        """
        Создает Product из словаря (фабричный метод).

        Args:
            data: Словарь с данными товара

        Returns:
            Product: Новый экземпляр товара
        """
        return cls(
            product_id=int(data['id']),
            name=str(data['name']),
            category=str(data.get('category', 'Разное')),
            price=Decimal(str(data['price'])),
            stock=int(data['stock']),
            image_url=data.get('image_url'),
        )

    def to_dict(self) -> dict:
        """
        Преобразует Product в словарь.

        Returns:
            dict: Данные товара
        """
        return {
            'id': self.product_id,
            'name': self.name,
            'category': self.category,
            'price': float(self.price),
            'stock': self.stock,
            'image_url': self.image_url or '',
        }