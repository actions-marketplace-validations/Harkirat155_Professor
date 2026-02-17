"""Analyzers module initialization."""

from professor.analyzers.llm_analyzer import LLMAnalyzer
from professor.analyzers.security_analyzer import SecurityAnalyzer
from professor.analyzers.complexity_analyzer import ComplexityAnalyzer
from professor.analyzers.language_tool_analyzers import (
    CppStaticAnalyzer,
    ESLintAnalyzer,
    GoStaticAnalyzer,
    JavaStaticAnalyzer,
    RustStaticAnalyzer,
)

try:
    from professor.analyzers.ruff_analyzer import RuffAnalyzer

    __all__ = [
        "LLMAnalyzer",
        "SecurityAnalyzer",
        "ComplexityAnalyzer",
        "RuffAnalyzer",
        "ESLintAnalyzer",
        "JavaStaticAnalyzer",
        "GoStaticAnalyzer",
        "CppStaticAnalyzer",
        "RustStaticAnalyzer",
    ]
except ImportError:
    __all__ = [
        "LLMAnalyzer",
        "SecurityAnalyzer",
        "ComplexityAnalyzer",
        "ESLintAnalyzer",
        "JavaStaticAnalyzer",
        "GoStaticAnalyzer",
        "CppStaticAnalyzer",
        "RustStaticAnalyzer",
    ]
