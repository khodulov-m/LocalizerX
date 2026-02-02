"""Data class for app context used in screenshot text generation."""

from __future__ import annotations

from dataclasses import dataclass

from localizerx.parser.metadata_model import LocaleMetadata, MetadataFieldType


@dataclass
class AppContext:
    """Context about the app for generating screenshot texts.

    Contains key app information extracted from fastlane metadata that helps
    the AI generate relevant, on-brand screenshot marketing copy.
    """

    name: str
    subtitle: str | None = None
    promo_text: str | None = None
    description: str | None = None
    keywords: list[str] | None = None

    @classmethod
    def from_metadata(cls, metadata: LocaleMetadata) -> "AppContext":
        """Create AppContext from fastlane LocaleMetadata.

        Args:
            metadata: LocaleMetadata object containing app metadata fields

        Returns:
            AppContext populated with available metadata
        """
        name_field = metadata.get_field(MetadataFieldType.NAME)
        subtitle_field = metadata.get_field(MetadataFieldType.SUBTITLE)
        promo_field = metadata.get_field(MetadataFieldType.PROMOTIONAL_TEXT)
        desc_field = metadata.get_field(MetadataFieldType.DESCRIPTION)
        keywords_field = metadata.get_field(MetadataFieldType.KEYWORDS)

        # Parse keywords from comma-separated string
        keywords = None
        if keywords_field and keywords_field.content:
            keywords = [k.strip() for k in keywords_field.content.split(",") if k.strip()]

        return cls(
            name=name_field.content if name_field else "App",
            subtitle=subtitle_field.content if subtitle_field else None,
            promo_text=promo_field.content if promo_field else None,
            description=desc_field.content if desc_field else None,
            keywords=keywords,
        )

    @property
    def description_summary(self) -> str | None:
        """Get a shortened description for prompts (first 500 chars).

        Returns:
            Truncated description or None if no description exists
        """
        if not self.description:
            return None
        if len(self.description) <= 500:
            return self.description
        # Truncate at word boundary
        truncated = self.description[:500]
        last_space = truncated.rfind(" ")
        if last_space > 400:
            truncated = truncated[:last_space]
        return truncated + "..."

    def to_prompt_context(self) -> str:
        """Format app context for inclusion in generation prompts.

        Returns:
            Formatted string describing the app for prompt injection
        """
        lines = [f"- App Name: {self.name}"]

        if self.subtitle:
            lines.append(f"- Tagline: {self.subtitle}")

        if self.promo_text:
            lines.append(f"- Promo: {self.promo_text}")

        if self.description_summary:
            lines.append(f"- Description: {self.description_summary}")

        if self.keywords:
            # Include top keywords for context
            top_keywords = self.keywords[:10]
            lines.append(f"- Keywords: {', '.join(top_keywords)}")

        return "\n".join(lines)
