"""Tests for language capability matrix and analyzer routing."""

import pytest

from professor.core.analyzer import Analyzer
from professor.core.language_router import LanguageAnalyzerRouter, LanguageCapabilities


class DummyAnalyzer(Analyzer):
    """Minimal analyzer used for routing tests."""

    async def analyze(self, context):
        return []

    def supports(self, context):
        return context.get("enabled", True)


def test_router_returns_global_and_language_analyzers():
    router = LanguageAnalyzerRouter()
    global_analyzer = DummyAnalyzer()
    python_analyzer = DummyAnalyzer()

    router.register_global(global_analyzer)
    router.register_language("python", python_analyzer)

    analyzers = router.get_analyzers("python")
    assert len(analyzers) == 2
    assert global_analyzer in analyzers
    assert python_analyzer in analyzers


def test_router_filters_by_supports_with_context():
    router = LanguageAnalyzerRouter()
    analyzer = DummyAnalyzer()
    router.register_global(analyzer)

    enabled = router.get_analyzers("python", {"enabled": True})
    disabled = router.get_analyzers("python", {"enabled": False})

    assert len(enabled) == 1
    assert len(disabled) == 0


def test_capability_matrix_registration():
    router = LanguageAnalyzerRouter()
    router.set_capabilities(
        LanguageCapabilities(
            language="rust",
            lint=True,
            type_check=True,
            security_scan=True,
            semantic=True,
            tools=["clippy", "cargo-check"],
        )
    )

    capability = router.get_capabilities("rust")
    assert capability is not None
    assert capability.type_check
    assert "clippy" in capability.tools
    assert "rust" in router.list_languages()

