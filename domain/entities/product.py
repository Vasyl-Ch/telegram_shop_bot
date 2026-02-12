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
    brand: Optional[str] = None
    unit_of_measurement: str = "шт"
    size_or_weight: Optional[float] = None

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

        object.__setattr__(
            self, "unit_of_measurement", self.unit_of_measurement.lower().strip()
        )

        if self.unit_of_measurement not in ("шт", "кг"):
            raise ValueError(f"Invalid unit_of_measurement: {self.unit_of_measurement}")

    @property
    def is_available(self) -> bool:
        """
        Checking the availability of goods.

        Returns:
            bool: True if the product is in stock
        """
        return self.stock > 0

    @property
    def final_price_per_unit(self) -> Decimal:
        """
        Calculates final price per unit (kg or piece) based on measurement type.

        Logic:
        - If unit is "кг": return base price (already per kg)
        - If unit is "шт":
            - If size_or_weight < 30: it's volume, return base price (per piece)
            - If size_or_weight >= 30: it's weight in grams, calculate price per kg

        Returns:
            Decimal: Final price per unit
        """
        if self.unit_of_measurement == "кг":
            return self.price

        if self.size_or_weight is None:
            return self.price

        if self.size_or_weight < 30:
            return self.price
        else:
            weight_kg = Decimal(str(self.size_or_weight)) / Decimal("1000")
            if weight_kg > 0:
                return self.price / weight_kg
            return self.price

    @property
    def package_price(self) -> Decimal:
        """
        Calculates price for one package/unit of this product.

        Logic:
        - If unit is "кг" AND size_or_weight is set:
            price_per_kg × size_or_weight (kg) = price for this package
        - Otherwise: return base price (price per piece)

        Returns:
            Decimal: Price for one package
        """
        if self.unit_of_measurement == "кг" and self.size_or_weight:
            result = self.price * Decimal(str(self.size_or_weight))

            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                f"Product {self.product_id} ({self.name}): "
                f"price_per_kg={self.price}, weight={self.size_or_weight}кг, "
                f"package_price={result}"
            )
            return result

        return self.price

    @property
    def display_price(self) -> str:
        """
        Formatted price to display.

        For "кг" products shows: "100₴/кг (250₴ за 2.5кг)"
        For "шт" products shows: "50₴/шт" or "200₴/кг (50₴ за 250г)"
        """
        if self.unit_of_measurement == "кг":
            if self.size_or_weight and self.size_or_weight > 0:
                package_price = self.package_price
                return f"{self.price:.2f}₴/кг ({package_price:.2f}₴ за {self.measurement_info})"
            return f"{self.price:.2f}₴/кг"

        if self.size_or_weight is not None and self.size_or_weight >= 30:
            price_per_kg = self.final_price_per_unit
            return (
                f"{price_per_kg:.2f}₴/кг ({self.price:.2f}₴ за {self.measurement_info})"
            )

        return f"{self.price:.2f}₴/шт"

    @property
    def stock_status(self) -> str:
        """
        Availability status of the product.

        Returns:
            str: Textual description of the status
        """
        if self.stock == 0:
            return "❌ Нет в наличии"
        elif self.stock <= 5 and self.unit_of_measurement == "кг":
            return f"⚠️ Осталось {self.stock} кг."
        elif self.stock <= 5 and self.unit_of_measurement == "шт":
            return f"⚠️ Осталось {self.stock} шт."
        else:
            return f"✅ В наличии ({self.stock} шт.)"

    @property
    def measurement_info(self) -> str:
        """
        Returns measurement information for display.

        Returns:
            str: Measurement details (e.g., "2.5кг", "0.5л", "250г")
        """
        if self.size_or_weight is None:
            return f"1 {self.unit_of_measurement}"

        if self.unit_of_measurement == "кг":
            return f"{self.size_or_weight}кг"

        if self.size_or_weight < 30:
            return f"{self.size_or_weight}л"
        else:
            return f"{int(self.size_or_weight)}грамм"

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

        Logic:
        - If unit is "кг" AND size_or_weight is set:
            Uses package_price (price_per_kg × kg_per_package) × quantity
        - Otherwise: base_price × quantity

        Args:
            quantity: Number of packages/pieces

        Returns:
            Decimal: Total cost
        """
        return self.package_price * quantity

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
            brand=data.get("brand"),
            unit_of_measurement=str(data.get("unit_of_measurement", "шт")),
            size_or_weight=(
                float(data["size_or_weight"]) if data.get("size_or_weight") else None
            ),
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
            "brand": self.brand or "",
            "unit_of_measurement": self.unit_of_measurement,
            "size_or_weight": self.size_or_weight,
        }
