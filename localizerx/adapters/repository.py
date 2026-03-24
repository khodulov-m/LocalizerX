"""Concrete repository implementations."""

from pathlib import Path

from localizerx.core.ports.repository import CatalogRepository
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.model import StringCatalog


class XCStringsRepository(CatalogRepository):
    """Repository implementation for Xcode String Catalogs (.xcstrings)."""

    def read(self, path: Path) -> StringCatalog:
        """Read a .xcstrings file."""
        return read_xcstrings(path)

    def write(self, catalog: StringCatalog, path: Path, backup: bool = False) -> None:
        """Write a .xcstrings file."""
        write_xcstrings(catalog, path, backup=backup)
