"""Translation adapters."""

from .base import Translator
from .gemini_adapter import GeminiTranslator

__all__ = ["Translator", "GeminiTranslator"]
