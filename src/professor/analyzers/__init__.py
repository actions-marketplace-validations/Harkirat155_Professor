"""Analyzers module initialization."""

from professor.analyzers.llm_analyzer import LLMAnalyzer
from professor.analyzers.security_analyzer import SecurityAnalyzer
from professor.analyzers.complexity_analyzer import ComplexityAnalyzer

try:
    from professor.analyzers.ruff_analyzer import RuffAnalyzer

    __all__ = ["LLMAnalyzer", "SecurityAnalyzer", "ComplexityAnalyzer", "RuffAnalyzer"]
except ImportError:
    __all__ = ["LLMAnalyzer", "SecurityAnalyzer", "ComplexityAnalyzer"]
