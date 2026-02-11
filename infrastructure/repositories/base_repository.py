"""
Basic abstract repository.

Applications of SOLID:
- Interface Segregation: A minimum set of methods
- Dependency Inversion: Dependency on Abstraction
- Single Responsibility: CRUD operations only

Repository pattern:
- Abstracts data storage logic
- Easy to replace implementation (in-memory → DB)
- Centralizes access to data
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

# Generic type for entity
T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository.

    Generic class - can work with any type of entity.

    Type Parameters:
        T: Entity type (Order, Cart, Product, etc.)
    """

    @abstractmethod
    def save(self, entity: T) -> T:
        """
        Saves the entity.

        Args:
            entity: Entity to save

        Returns:
            T: Saved entity (with updated fields if needed)
        """
        pass

    @abstractmethod
    def get_by_id(self, entity_id: int) -> Optional[T]:
        """
        Gets entity by ID.

        Args:
            entity_id: Unique identifier

        Returns:
            Optional[T]: Entity if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """
        Gets all entity.

        Returns:
            List[T]: List of all entities
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Updates an existing entity.

        Args:
            entity: Entity with updated data

        Returns:
            T: Updated entity
        """
        pass

    @abstractmethod
    def delete(self, entity_id: int) -> bool:
        """
        Deletes entity by ID.

        Args:
            entity_id: Entity ID to delete

        Returns:
            bool: True if removed, False if not found
        """
        pass

    @abstractmethod
    def exists(self, entity_id: int) -> bool:
        """
        Checks for the existence of an entity.

        Args:
            entity_id: ID entity

        Returns:
            bool: True if exists
        """
        pass
