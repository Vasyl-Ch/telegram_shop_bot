"""
Cart entity (корзина покупок).

Применение DDD:
- Cart - это Aggregate Root (управляет CartItem'ами)
- Инкапсулирует логику добавления/удаления товаров
- Валидирует бизнес-правила
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional


@dataclass
class CartItem:
    """
    Товар в корзине.

    Value Object - идентифицируется по product_id.
    """

    product_id: int
    """ID товара."""

    name: str
    """Название товара (кеш для отображения)."""

    price: Decimal
    """Цена за единицу."""

    quantity: int
    """Количество в корзине."""

    max_available: int
    """Максимально доступное количество на складе."""

    def __post_init__(self):
        """Валидация."""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.quantity > self.max_available:
            raise ValueError(
                f"Cannot add {self.quantity} items. "
                f"Only {self.max_available} available."
            )

    @property
    def total(self) -> Decimal:
        """Стоимость позиции."""
        return self.price * self.quantity

    def can_increase(self) -> bool:
        """Можно ли увеличить количество."""
        return self.quantity < self.max_available

    def increase(self) -> 'CartItem':
        """
        Увеличивает количество на 1.

        Returns:
            CartItem: Новый экземпляр с увеличенным количеством

        Raises:
            ValueError: Если достигнут максимум
        """
        if not self.can_increase():
            raise ValueError("Maximum available quantity reached")

        return CartItem(
            product_id=self.product_id,
            name=self.name,
            price=self.price,
            quantity=self.quantity + 1,
            max_available=self.max_available,
        )

    def decrease(self) -> Optional['CartItem']:
        """
        Уменьшает количество на 1.

        Returns:
            CartItem: Новый экземпляр с уменьшенным количеством,
                      или None если количество станет 0
        """
        if self.quantity <= 1:
            return None

        return CartItem(
            product_id=self.product_id,
            name=self.name,
            price=self.price,
            quantity=self.quantity - 1,
            max_available=self.max_available,
        )


@dataclass
class Cart:
    """
    Корзина покупок (Aggregate Root).

    Управляет коллекцией CartItem и обеспечивает
    согласованность данных.
    """

    chat_id: int
    """ID пользователя-владельца корзины."""

    items: Dict[int, CartItem] = field(default_factory=dict)
    """Товары в корзине (key: product_id, value: CartItem)."""

    def add_item(self, cart_item: CartItem) -> None:
        """
        Добавляет товар в корзину или увеличивает количество.

        Args:
            cart_item: Товар для добавления

        Raises:
            ValueError: Если превышено доступное количество
        """
        product_id = cart_item.product_id

        if product_id in self.items:
            # Товар уже в корзине - увеличиваем количество
            existing = self.items[product_id]
            self.items[product_id] = existing.increase()
        else:
            # Новый товар
            self.items[product_id] = cart_item

    def remove_item(self, product_id: int) -> None:
        """
        Уменьшает количество товара или удаляет из корзины.

        Args:
            product_id: ID товара
        """
        if product_id not in self.items:
            return

        decreased = self.items[product_id].decrease()
        if decreased is None:
            del self.items[product_id]
        else:
            self.items[product_id] = decreased

    def delete_item(self, product_id: int) -> None:
        """
        Полностью удаляет товар из корзины.

        Args:
            product_id: ID товара
        """
        self.items.pop(product_id, None)

    def clear(self) -> None:
        """Очищает корзину."""
        self.items.clear()

    def is_empty(self) -> bool:
        """Проверяет, пуста ли корзина."""
        return len(self.items) == 0

    def get_total(self) -> Decimal:
        """
        Вычисляет общую стоимость корзины.

        Returns:
            Decimal: Общая сумма
        """
        return sum(item.total for item in self.items.values())

    def get_items_count(self) -> int:
        """
        Подсчитывает общее количество товаров.

        Returns:
            int: Количество единиц товара
        """
        return sum(item.quantity for item in self.items.values())

    def get_items_list(self) -> List[CartItem]:
        """
        Возвращает список товаров в корзине.

        Returns:
            List[CartItem]: Список товаров
        """
        return list(self.items.values())

    def validate_against_stock(self, stock_checker) -> List[str]:
        """
        Проверяет, все ли товары доступны в нужном количестве.

        Args:
            stock_checker: Функция для проверки остатков
                          (product_id: int) -> int (available stock)

        Returns:
            List[str]: Список ошибок (пустой если все ОК)
        """
        errors = []

        for product_id, cart_item in self.items.items():
            available = stock_checker(product_id)

            if available == 0:
                errors.append(
                    f"❌ {cart_item.name} - нет в наличии"
                )
            elif available < cart_item.quantity:
                errors.append(
                    f"⚠️ {cart_item.name} - доступно только {available} шт. "
                    f"(в корзине {cart_item.quantity} шт.)"
                )

        return errors