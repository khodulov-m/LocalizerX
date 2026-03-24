"""Concrete repository implementations."""

from pathlib import Path

from localizerx.core.ports.repository import CatalogRepository
from localizerx.io.android import read_android, write_android
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.android_model import AndroidCatalog
from localizerx.parser.model import StringCatalog


class XCStringsRepository(CatalogRepository[StringCatalog]):
    """Repository implementation for Xcode String Catalogs (.xcstrings)."""

    def read(self, path: Path, **kwargs) -> StringCatalog:
        """Read a .xcstrings file."""
        return read_xcstrings(path)

    def write(self, catalog: StringCatalog, path: Path, backup: bool = False, **kwargs) -> None:
        """Write a .xcstrings file."""
        write_xcstrings(catalog, path, backup=backup)


class AndroidCatalogRepository(CatalogRepository[AndroidCatalog]):
    """Repository implementation for Android strings.xml resources."""

    def read(self, path: Path, **kwargs) -> AndroidCatalog:
        """Read Android resources."""
        source_locale = kwargs.get("source_locale", "en")
        return read_android(path, source_locale=source_locale)

    def write(self, catalog: AndroidCatalog, path: Path, backup: bool = False, **kwargs) -> None:
        """Write Android resources."""
        locales = kwargs.get("locales")
        write_android(catalog, path, backup=backup, locales=locales)
