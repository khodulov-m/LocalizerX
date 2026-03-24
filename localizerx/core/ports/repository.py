"""Repository interfaces for data persistence."""

from abc import ABC, abstractmethod
from pathlib import Path

from localizerx.parser.model import StringCatalog


class CatalogRepository(ABC):
    """Abstract interface for catalog storage and retrieval."""

    @abstractmethod
    def read(self, path: Path) -> StringCatalog:
        """
        Read a catalog from the specified path.
        
        Args:
            path: Path to the catalog file
            
        Returns:
            The parsed StringCatalog
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file cannot be parsed
        """
        ...

    @abstractmethod
    def write(self, catalog: StringCatalog, path: Path, backup: bool = False) -> None:
        """
        Write a catalog to the specified path.
        
        Args:
            catalog: The StringCatalog to write
            path: Path to write the catalog to
            backup: Whether to create a backup of the existing file
        """
        ...
