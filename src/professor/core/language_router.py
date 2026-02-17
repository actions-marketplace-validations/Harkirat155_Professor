"""Language capability matrix and analyzer router."""

from dataclasses import dataclass, field
from typing import Any

from professor.core.analyzer import Analyzer


@dataclass(frozen=True)
class LanguageCapabilities:
    """Capabilities available for a programming language."""

    language: str
    lint: bool = False
    type_check: bool = False
    security_scan: bool = False
    complexity: bool = False
    semantic: bool = False
    tools: list[str] = field(default_factory=list)


class LanguageAnalyzerRouter:
    """Routes analyzers by language while preserving shared analyzers."""

    def __init__(self) -> None:
        self._global_analyzers: list[Analyzer] = []
        self._language_analyzers: dict[str, list[Analyzer]] = {}
        self._capabilities: dict[str, LanguageCapabilities] = {}

    def register_global(self, analyzer: Analyzer) -> None:
        """Register analyzer that applies to all languages."""
        self._global_analyzers.append(analyzer)

    def register_language(self, language: str, analyzer: Analyzer) -> None:
        """Register analyzer for a specific language."""
        key = language.lower()
        self._language_analyzers.setdefault(key, []).append(analyzer)

    def set_capabilities(self, capabilities: LanguageCapabilities) -> None:
        """Register/overwrite language capabilities."""
        self._capabilities[capabilities.language.lower()] = capabilities

    def get_capabilities(self, language: str) -> LanguageCapabilities | None:
        """Get capability info for a language."""
        return self._capabilities.get(language.lower())

    def list_languages(self) -> list[str]:
        """List languages with registered capabilities."""
        return sorted(self._capabilities.keys())

    def get_analyzers(
        self, language: str, context: dict[str, Any] | None = None
    ) -> list[Analyzer]:
        """Get analyzers applicable to language and optional context."""
        key = language.lower()
        analyzers = [
            *self._global_analyzers,
            *self._language_analyzers.get(key, []),
        ]
        if context is None:
            return analyzers
        return [analyzer for analyzer in analyzers if analyzer.supports(context)]

