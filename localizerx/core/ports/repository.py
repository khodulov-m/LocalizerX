"""Repository interfaces for data persistence."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")


class CatalogRepository(ABC, Generic[T]):
    """Abstract interface for catalog storage and retrieval."""

    @abstractmethod
    def read(self, path: Path, **kwargs) -> T:
        """
        Read a catalog from the specified path.
        
        Args:
            path: Path to the catalog file
            **kwargs: Implementation specific arguments (e.g. source_locale)
            
        Returns:
            The parsed catalog
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file cannot be parsed
        """
        ...

    @abstractmethod
    def write(self, catalog: T, path: Path, backup: bool = False, **kwargs) -> None:
        """
        Write a catalog to the specified path.
        
        Args:
            catalog: The catalog to write
            path: Path to write the catalog to
            backup: Whether to create a backup of the existing file
            **kwargs: Implementation specific arguments
        """
        ...
