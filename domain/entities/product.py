"""
Product entity (domain model of the product).

Applications of DDD (Domain-Driven Design):
- The product is a Value Object (identified by ID)
- Immutable for thread safety
- Encapsulates the business logic of the product
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Product:
    """
    Domain model of the product.

    Why frozen=True:
    - Thread safety (immutable)
    - Prevents accidental change
    - Can be used as a key in dict/set

    Why Decimal for Pricing:
    - Precise arithmetic for monetary transactions
    - Avoiding float problems (0.1 + 0.2 != 0.3)
    """

    product_id: int
    name: str
    category: str
    price: Decimal
    stock: int
    image_url: Optional[str] = None

    def __post_init__(self):
        """
        Validation after initialization.

        Raises:
            ValueError: If the data is invalid
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
        Checking the availability of goods.

        Returns:
            bool: True if the product is in stock
        """
        return self.stock > 0

    @property
    def display_price(self) -> str:
        """
        Formatted price to display.

        Returns:
            str: Price with currency
        """
        return f"{self.price:.2f}"

    @property
    def stock_status(self) -> str:
        """
        Availability status of the product.

        Returns:
            str: Textual description of the status
        """
        if self.stock == 0:
            return "❌ Нет в наличии"
        elif self.stock <= 5:
            return f"⚠️ Осталось {self.stock} шт."
        else:
            return f"✅ В наличии ({self.stock} шт.)"

    def can_fulfill_quantity(self, quantity: int) -> bool:
        """
        Checks the ability to fulfill the order for the specified quantity.

        Args:
            quantity: Required quantity

        Returns:
            bool: True if there are enough goods in stock
        """
        return self.stock >= quantity

    def calculate_total(self, quantity: int) -> Decimal:
        """
        Calculates the cost for the specified quantity.

        Args:
            quantity: Quantity of goods

        Returns:
            Decimal: Total Cost
        """
        return self.price * quantity

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        """
        Creates a Product from a dictionary (factory method).

        Args:
            data: Dictionary with product data

        Returns:
            Product: A new copy of the product
        """
        return cls(
            product_id=int(data["id"]),
            name=str(data["name"]),
            category=str(data.get("category", "Разное")),
            price=Decimal(str(data["price"])),
            stock=int(data["stock"]),
            image_url=data.get("image_url"),
        )

    def to_dict(self) -> dict:
        """
        Converts Product to a dictionary.

        Returns:
            dict: Product data
        """
        return {
            "id": self.product_id,
            "name": self.name,
            "category": self.category,
            "price": float(self.price),
            "stock": self.stock,
            "image_url": self.image_url or "",
        }
