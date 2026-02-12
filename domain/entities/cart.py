"""
Cart entity.

Applications of DDD:
- Cart is Aggregate Root (manages CartItems)
- Encapsulates the logic of adding/removing products
- Validates business rules
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional


@dataclass
class CartItem:
    """
    The product is in the cart.

    Value Object - identified by product_id.
    Stores package_price for correct calculation when product has weight.
    """

    product_id: int
    name: str
    price: Decimal
    quantity: int
    max_available: int

    unit_of_measurement: str = "шт"
    size_or_weight: Optional[float] = None

    def __post_init__(self):
        """Validation."""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.quantity > self.max_available:
            raise ValueError(
                f"Cannot add {self.quantity} items. "
                f"Only {self.max_available} available."
            )

    @property
    def total(self) -> Decimal:
        """Position value."""
        return self.price * self.quantity

    @property
    def display_info(self) -> str:
        """
        Returns display information about the item.

        Returns:
            str: e.g., "×2 шт" or "×3 (по 2.5кг)"
        """
        if self.unit_of_measurement == "кг" and self.size_or_weight:
            return f"×{self.quantity} (по {self.size_or_weight}кг)"
        return f"×{self.quantity} шт"

    def can_increase(self) -> bool:
        """Is it possible to increase the number."""
        return self.quantity < self.max_available

    def increase(self) -> "CartItem":
        """
        Increases the quantity by 1.

        Returns:
            CartItem: New instance with increased quantity

        Raises:
            ValueError: If the maximum is reached
        """
        if not self.can_increase():
            raise ValueError("Maximum available quantity reached")

        return CartItem(
            product_id=self.product_id,
            name=self.name,
            price=self.price,
            quantity=self.quantity + 1,
            max_available=self.max_available,
            unit_of_measurement=self.unit_of_measurement,
            size_or_weight=self.size_or_weight,
        )

    def decrease(self) -> Optional["CartItem"]:
        """
        Decreases the amount by 1.

        Returns:
            CartItem: A new instance with a reduced quantity,
                      or None if the count becomes 0
        """
        if self.quantity <= 1:
            return None

        return CartItem(
            product_id=self.product_id,
            name=self.name,
            price=self.price,
            quantity=self.quantity - 1,
            max_available=self.max_available,
            unit_of_measurement=self.unit_of_measurement,
            size_or_weight=self.size_or_weight,
        )


@dataclass
class Cart:
    """
    Shopping cart (Aggregate Root).

    Manages the CartItem collection and provides
    data consistency.
    """

    chat_id: int
    items: Dict[int, CartItem] = field(default_factory=dict)

    def add_item(self, cart_item: CartItem) -> None:
        """
        Adds an item to the cart or increases the quantity.

        Args:
            cart_item: Product to add

        Raises:
            ValueError: If the available quantity is exceeded
        """
        product_id = cart_item.product_id

        if product_id in self.items:
            existing = self.items[product_id]
            self.items[product_id] = existing.increase()
        else:
            self.items[product_id] = cart_item

    def remove_item(self, product_id: int) -> None:
        """
        Reduces the quantity of the product or removes it from the cart.

        Args:
            product_id: Product ID
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
        Completely removes the product from the cart.

        Args:
            product_id: Product ID
        """
        self.items.pop(product_id, None)

    def clear(self) -> None:
        """Empties the trash."""
        self.items.clear()

    def is_empty(self) -> bool:
        """Checks if the cart is empty."""
        return len(self.items) == 0

    def get_total(self) -> Decimal:
        """
        Calculates the total cost of the cart.

        Returns:
            Decimal: Total amount
        """
        return sum(item.total for item in self.items.values())

    def get_items_count(self) -> int:
        """
        Counts the total number of products.

        Returns:
            int: Number of units of the product
        """
        return sum(item.quantity for item in self.items.values())

    def get_items_list(self) -> List[CartItem]:
        """
        Returns a list of items in the cart.

        Returns:
            List[CartItem]: List of products
        """
        return list(self.items.values())

    def validate_against_stock(self, stock_checker) -> List[str]:
        """
        Checks if all products are available in the right quantity.

        Args:
            stock_checker: Function for checking balances
                          (product_id: int) -> int (available stock)

        Returns:
            List[str]: List of errors (empty if everything is OK)
        """
        errors = []

        for product_id, cart_item in self.items.items():
            available = stock_checker(product_id)

            if available == 0:
                errors.append(f"❌ {cart_item.name} - нет в наличии")
            elif available < cart_item.quantity:
                errors.append(
                    f"⚠️ {cart_item.name} - доступно только {available} шт. "
                    f"(в корзине {cart_item.quantity} шт.)"
                )

        return errors
