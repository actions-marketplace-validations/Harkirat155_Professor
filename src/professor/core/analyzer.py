"""Base analyzer interface and abstract classes."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional
from professor.core.models import Finding, Review


class AnalyzerConfig(ABC):
    """Base configuration for analyzers."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize analyzer configuration."""
        for key, value in kwargs.items():
            setattr(self, key, value)


class Analyzer(ABC):
    """Abstract base class for all code analyzers."""

    def __init__(self, config: Optional[AnalyzerConfig] = None) -> None:
        """Initialize the analyzer.

        Args:
            config: Optional configuration for the analyzer
        """
        self.config = config or AnalyzerConfig()
        self.name = self.__class__.__name__

    @abstractmethod
    async def analyze(self, context: dict[str, Any]) -> list[Finding]:
        """Analyze code and return findings.

        Args:
            context: Analysis context containing code, files, metadata, etc.

        Returns:
            List of findings discovered during analysis

        Raises:
            AnalyzerError: If analysis fails
        """
        pass

    @abstractmethod
    def supports(self, context: dict[str, Any]) -> bool:
        """Check if this analyzer supports the given context.

        Args:
            context: Analysis context to check

        Returns:
            True if this analyzer can handle the context, False otherwise
        """
        pass

    def get_name(self) -> str:
        """Get the name of this analyzer."""
        return self.name

    def __str__(self) -> str:
        """String representation of the analyzer."""
        return f"{self.__class__.__name__}()"


class CompositeAnalyzer(Analyzer):
    """Analyzer that runs multiple sub-analyzers."""

    def __init__(
        self, analyzers: list[Analyzer], config: Optional[AnalyzerConfig] = None
    ) -> None:
        """Initialize composite analyzer.

        Args:
            analyzers: List of analyzers to run
            config: Optional configuration
        """
        super().__init__(config)
        self.analyzers = analyzers

    async def analyze(self, context: dict[str, Any]) -> list[Finding]:
        """Run all sub-analyzers and aggregate findings.

        Args:
            context: Analysis context

        Returns:
            Aggregated list of findings from all analyzers
        """
        applicable = [analyzer for analyzer in self.analyzers if analyzer.supports(context)]
        if not applicable:
            return []

        results = await asyncio.gather(
            *(analyzer.analyze(context) for analyzer in applicable)
        )

        all_findings: list[Finding] = []
        for findings in results:
            all_findings.extend(findings)
        return all_findings

    def supports(self, context: dict[str, Any]) -> bool:
        """Check if any sub-analyzer supports the context.

        Args:
            context: Analysis context

        Returns:
            True if at least one sub-analyzer supports the context
        """
        return any(analyzer.supports(context) for analyzer in self.analyzers)

    def __str__(self) -> str:
        """String representation."""
        analyzer_names = [a.get_name() for a in self.analyzers]
        return f"CompositeAnalyzer({', '.join(analyzer_names)})"


class AnalyzerError(Exception):
    """Base exception for analyzer errors."""

    pass


class AnalyzerTimeoutError(AnalyzerError):
    """Raised when analyzer exceeds time limit."""

    pass


class AnalyzerConfigError(AnalyzerError):
    """Raised when analyzer configuration is invalid."""

    pass
