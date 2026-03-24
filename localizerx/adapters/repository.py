"""Concrete repository implementations."""

from pathlib import Path

from localizerx.core.ports.repository import CatalogRepository
from localizerx.io.android import read_android, write_android
from localizerx.io.extension import read_extension, write_extension
from localizerx.io.frameit import read_frameit_catalog, write_frameit_locale
from localizerx.io.i18n import read_i18n, write_i18n
from localizerx.io.metadata import read_metadata, write_metadata
from localizerx.io.screenshots import read_screenshots, write_screenshots
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.android_model import AndroidCatalog
from localizerx.parser.extension_model import ExtensionCatalog
from localizerx.parser.frameit_model import FrameitCatalog
from localizerx.parser.i18n_model import I18nCatalog
from localizerx.parser.metadata_model import MetadataCatalog
from localizerx.parser.model import StringCatalog
from localizerx.parser.screenshots_model import ScreenshotsCatalog


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


class ExtensionCatalogRepository(CatalogRepository[ExtensionCatalog]):
    """Repository implementation for Chrome Extension locale files."""

    def read(self, path: Path, **kwargs) -> ExtensionCatalog:
        """Read Chrome Extension locales."""
        source_locale = kwargs.get("source_locale", "en")
        return read_extension(path, source_locale=source_locale)

    def write(self, catalog: ExtensionCatalog, path: Path, backup: bool = False, **kwargs) -> None:
        """Write Chrome Extension locales."""
        locales = kwargs.get("locales")
        write_extension(catalog, path, backup=backup, locales=locales)


class I18nCatalogRepository(CatalogRepository[I18nCatalog]):
    """Repository implementation for frontend i18n JSON files."""

    def read(self, path: Path, **kwargs) -> I18nCatalog:
        """Read i18n JSON locales."""
        source_locale = kwargs.get("source_locale", "en")
        return read_i18n(path, source_locale=source_locale)

    def write(self, catalog: I18nCatalog, path: Path, backup: bool = False, **kwargs) -> None:
        """Write i18n JSON locales."""
        locales = kwargs.get("locales")
        write_i18n(catalog, path, backup=backup, locales=locales)


class MetadataCatalogRepository(CatalogRepository[MetadataCatalog]):
    """Repository implementation for App Store metadata."""

    def read(self, path: Path, **kwargs) -> MetadataCatalog:
        """Read App Store metadata."""
        source_locale = kwargs.get("source_locale", "en-US")
        return read_metadata(path, source_locale=source_locale)

    def write(self, catalog: MetadataCatalog, path: Path, backup: bool = False, **kwargs) -> None:
        """Write App Store metadata."""
        write_metadata(catalog, path)


class ScreenshotsCatalogRepository(CatalogRepository[ScreenshotsCatalog]):
    """Repository implementation for App Store screenshot texts."""

    def read(self, path: Path, **kwargs) -> ScreenshotsCatalog:
        """Read screenshot texts."""
        return read_screenshots(path)

    def write(self, catalog: ScreenshotsCatalog, path: Path, backup: bool = False, **kwargs) -> None:
        """Write screenshot texts."""
        write_screenshots(catalog, path)


class FrameitCatalogRepository(CatalogRepository[FrameitCatalog]):
    """Repository implementation for fastlane frameit strings."""

    def read(self, path: Path, **kwargs) -> FrameitCatalog:
        """Read frameit strings."""
        source_locale = kwargs.get("source_locale", "en-US")
        return read_frameit_catalog(path, source_locale=source_locale)

    def write(self, catalog: FrameitCatalog, path: Path, backup: bool = False, **kwargs) -> None:
        """Write frameit strings."""
        for locale_data in catalog.locales.values():
            write_frameit_locale(path, locale_data)
