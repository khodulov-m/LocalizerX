
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
import tempfile
import shutil

from localizerx.core.use_cases.translate_metadata import (
    TranslateMetadataUseCase,
    TranslateMetadataRequest,
    MetadataTranslationTask,
    MetadataTranslationPreview,
    LimitAction
)
from localizerx.parser.metadata_model import (
    MetadataCatalog, 
    LocaleMetadata, 
    MetadataFieldType,
    FIELD_LIMITS
)

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    return repo

@pytest.fixture
def mock_translator():
    translator = MagicMock()
    translator._call_api = AsyncMock()
    # Need to mock __aenter__ and __aexit__ for 'async with'
    translator.__aenter__ = AsyncMock(return_value=translator)
    translator.__aexit__ = AsyncMock(return_value=None)
    return translator

@pytest.fixture
def sample_catalog():
    catalog = MetadataCatalog(source_locale="en-US")
    en_locale = LocaleMetadata(locale="en-US")
    en_locale.set_field(MetadataFieldType.NAME, "English Name")
    en_locale.set_field(MetadataFieldType.SUBTITLE, "English Subtitle")
    catalog.locales["en-US"] = en_locale
    return catalog

@pytest.mark.asyncio
async def test_execute_success(mock_repo, mock_translator, sample_catalog):
    """Test successful translation without dry-run."""
    mock_repo.read.return_value = sample_catalog
    
    # Mock to handle single and batch calls
    async def mock_call(prompt):
        if "<<ITEM_1>>" in prompt:
            return "<<ITEM_1>>German Name<</ITEM_1>>\n<<ITEM_2>>German Subtitle<</ITEM_2>>"
        return "German Translation"
    
    mock_translator._call_api.side_effect = mock_call
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        request = TranslateMetadataRequest(
            path=path,
            source_locale="en-US",
            target_locales=["de-DE"],
            dry_run=False
        )
        
        result = await use_case.execute(request)
        
        assert result.saved is True
        assert mock_repo.write.called
        # Check that we called _call_api for the translation
        assert mock_translator._call_api.called

@pytest.mark.asyncio
async def test_execute_character_limit_warn(mock_repo, mock_translator, sample_catalog):
    """Test character limit warning."""
    mock_repo.read.return_value = sample_catalog
    
    # Return a string that is too long (Name limit is 30)
    async def mock_call(prompt):
        if "<<ITEM_1>>" in prompt:
            return f"<<ITEM_1>>{'X' * 35}<</ITEM_1>>\n<<ITEM_2>>Subtitle<</ITEM_2>>"
        return "X" * 35
        
    mock_translator._call_api.side_effect = mock_call
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        request = TranslateMetadataRequest(
            path=Path(tmpdir),
            source_locale="en-US",
            target_locales=["de-DE"],
            limit_action=LimitAction.WARN,
            dry_run=False
        )
        
        result = await use_case.execute(request)
        
        assert len(result.limit_warnings) > 0
        assert "over by 5" in result.limit_warnings[0]
        assert result.saved is True
        # Verify it was saved with the long string
        written_catalog = mock_repo.write.call_args[0][0]
        assert len(written_catalog.get_locale("de-DE").get_field(MetadataFieldType.NAME).content) == 35

@pytest.mark.asyncio
async def test_execute_character_limit_truncate(mock_repo, mock_translator, sample_catalog):
    """Test character limit truncation."""
    mock_repo.read.return_value = sample_catalog
    
    async def mock_call(prompt):
        if "<<ITEM_1>>" in prompt:
            return f"<<ITEM_1>>{'X' * 40}<</ITEM_1>>\n<<ITEM_2>>Subtitle<</ITEM_2>>"
        return "X" * 40
        
    mock_translator._call_api.side_effect = mock_call
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        request = TranslateMetadataRequest(
            path=Path(tmpdir),
            source_locale="en-US",
            target_locales=["de-DE"],
            limit_action=LimitAction.TRUNCATE,
            dry_run=False
        )
        
        result = await use_case.execute(request)
        
        assert result.saved is True
        written_catalog = mock_repo.write.call_args[0][0]
        # Should be truncated to 30
        assert len(written_catalog.get_locale("de-DE").get_field(MetadataFieldType.NAME).content) == 30

@pytest.mark.asyncio
async def test_execute_character_limit_error(mock_repo, mock_translator, sample_catalog):
    """Test character limit error."""
    mock_repo.read.return_value = sample_catalog
    
    async def mock_call(prompt):
        if "<<ITEM_1>>" in prompt:
            return f"<<ITEM_1>>{'X' * 40}<</ITEM_1>>\n<<ITEM_2>>Subtitle<</ITEM_2>>"
        return "X" * 40
        
    mock_translator._call_api.side_effect = mock_call
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        request = TranslateMetadataRequest(
            path=Path(tmpdir),
            source_locale="en-US",
            target_locales=["de-DE"],
            limit_action=LimitAction.ERROR,
            dry_run=False
        )
        
        with pytest.raises(ValueError, match="Character limit exceeded"):
            await use_case.execute(request)

@pytest.mark.asyncio
async def test_execute_preview_apply(mock_repo, mock_translator, sample_catalog):
    """Test preview apply (True)."""
    mock_repo.read.return_value = sample_catalog
    mock_translator._call_api.return_value = "Translated"
    
    on_preview = MagicMock(return_value=True)
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        request = TranslateMetadataRequest(
            path=Path(tmpdir),
            source_locale="en-US",
            target_locales=["de-DE"],
            preview=True,
            dry_run=False
        )
        
        result = await use_case.execute(request, on_preview_request=on_preview)
        
        assert on_preview.called
        assert result.saved is True
        assert mock_repo.write.called

@pytest.mark.asyncio
async def test_execute_preview_cancel(mock_repo, mock_translator, sample_catalog):
    """Test preview cancel (False)."""
    mock_repo.read.return_value = sample_catalog
    mock_translator._call_api.return_value = "Translated"
    
    on_preview = MagicMock(return_value=False)
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        request = TranslateMetadataRequest(
            path=Path(tmpdir),
            source_locale="en-US",
            target_locales=["de-DE"],
            preview=True,
            dry_run=False
        )
        
        result = await use_case.execute(request, on_preview_request=on_preview)
        
        assert on_preview.called
        assert result.saved is False
        assert not mock_repo.write.called

@pytest.mark.asyncio
async def test_copy_untranslatable_files(mock_repo, mock_translator, sample_catalog):
    """Test copying of untranslatable files like privacy_url.txt."""
    mock_repo.read.return_value = sample_catalog
    mock_translator._call_api.return_value = "Translated"
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        # Create source directory and untranslatable file
        src_dir = path / "en-US"
        src_dir.mkdir()
        (src_dir / "privacy_url.txt").write_text("https://example.com/privacy")
        
        request = TranslateMetadataRequest(
            path=path,
            source_locale="en-US",
            target_locales=["de-DE"],
            dry_run=False
        )
        
        await use_case.execute(request)
        
        # Check if file was copied to target locale
        dst_file = path / "de-DE" / "privacy_url.txt"
        assert dst_file.exists()
        assert dst_file.read_text() == "https://example.com/privacy"

@pytest.mark.asyncio
async def test_execute_overwrite(mock_repo, mock_translator, sample_catalog):
    """Test overwrite flag."""
    # Add existing translations for ALL fields to German
    de_locale = LocaleMetadata(locale="de-DE")
    de_locale.set_field(MetadataFieldType.NAME, "Existing German Name")
    de_locale.set_field(MetadataFieldType.SUBTITLE, "Existing German Subtitle")
    sample_catalog.locales["de-DE"] = de_locale
    
    mock_repo.read.return_value = sample_catalog
    
    async def mock_call(prompt):
        if "<<ITEM_1>>" in prompt:
            return "<<ITEM_1>>New German Translation<</ITEM_1>>\n<<ITEM_2>>New German Translation<</ITEM_2>>"
        return "New German Translation"
    mock_translator._call_api.side_effect = mock_call
    
    use_case = TranslateMetadataUseCase(repository=mock_repo, translator=mock_translator)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Case 1: overwrite=False (default)
        request = TranslateMetadataRequest(
            path=Path(tmpdir),
            source_locale="en-US",
            target_locales=["de-DE"],
            overwrite=False,
            dry_run=False
        )
        result = await use_case.execute(request)
        # Should NOT have any tasks because German already had both fields
        assert not result.tasks
        assert result.saved is False
        
        # Case 2: overwrite=True
        request = TranslateMetadataRequest(
            path=Path(tmpdir),
            source_locale="en-US",
            target_locales=["de-DE"],
            overwrite=True,
            dry_run=False
        )
        result = await use_case.execute(request)
        assert result.saved is True
        written_catalog = mock_repo.write.call_args[0][0]
        assert written_catalog.get_locale("de-DE").get_field(MetadataFieldType.NAME).content == "New German Translation"
