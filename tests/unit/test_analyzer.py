"""Tests for analyzer base classes."""

import asyncio
import time
import pytest
from professor.core.analyzer import Analyzer, AnalyzerConfig, CompositeAnalyzer
from professor.core.models import Finding, FindingCategory, Location, Severity


class DummyAnalyzer(Analyzer):
    """Test analyzer implementation."""
    
    async def analyze(self, context):
        """Return dummy finding."""
        location = Location(file_path="test.py", line_start=1)
        return [
            Finding(
                id="test-1",
                severity=Severity.LOW,
                category=FindingCategory.STYLE,
                title="Test finding",
                message="This is a test",
                location=location,
                analyzer=self.name,
            )
        ]
    
    def supports(self, context):
        """Support Python files."""
        return context.get("language") == "python"


class AlwaysFailAnalyzer(Analyzer):
    """Analyzer that doesn't support anything."""
    
    async def analyze(self, context):
        """Never called."""
        return []
    
    def supports(self, context):
        """Never supports."""
        return False


class SlowAnalyzer(Analyzer):
    """Analyzer that simulates non-trivial async work."""

    async def analyze(self, context):
        await asyncio.sleep(0.1)
        location = Location(file_path="test.py", line_start=1)
        return [
            Finding(
                id="slow-1",
                severity=Severity.INFO,
                category=FindingCategory.PERFORMANCE,
                title="Slow finding",
                message="simulated",
                location=location,
                analyzer=self.name,
            )
        ]

    def supports(self, context):
        return True


@pytest.mark.asyncio
async def test_analyzer_basic():
    """Test basic analyzer functionality."""
    analyzer = DummyAnalyzer()
    
    # Test name
    assert analyzer.get_name() == "DummyAnalyzer"
    
    # Test supports
    assert analyzer.supports({"language": "python"})
    assert not analyzer.supports({"language": "javascript"})
    
    # Test analyze
    findings = await analyzer.analyze({"language": "python"})
    assert len(findings) == 1
    assert findings[0].title == "Test finding"


@pytest.mark.asyncio
async def test_composite_analyzer():
    """Test composite analyzer with multiple sub-analyzers."""
    analyzer1 = DummyAnalyzer()
    analyzer2 = DummyAnalyzer()
    
    composite = CompositeAnalyzer([analyzer1, analyzer2])
    
    # Test supports (should support if any sub-analyzer supports)
    assert composite.supports({"language": "python"})
    
    # Test analyze (should aggregate findings from all analyzers)
    findings = await composite.analyze({"language": "python"})
    assert len(findings) == 2
    
    # Test with unsupported context
    findings = await composite.analyze({"language": "javascript"})
    assert len(findings) == 0


@pytest.mark.asyncio
async def test_composite_analyzer_mixed():
    """Test composite with mix of supporting and non-supporting analyzers."""
    supporting = DummyAnalyzer()
    not_supporting = AlwaysFailAnalyzer()
    
    composite = CompositeAnalyzer([supporting, not_supporting])
    
    # Should still support if at least one supports
    assert composite.supports({"language": "python"})
    
    # Should only get findings from supporting analyzer
    findings = await composite.analyze({"language": "python"})
    assert len(findings) == 1


@pytest.mark.asyncio
async def test_composite_analyzer_runs_in_parallel():
    """Composite analyzer should run supported analyzers concurrently."""
    composite = CompositeAnalyzer([SlowAnalyzer(), SlowAnalyzer()])

    start = time.perf_counter()
    findings = await composite.analyze({"language": "python"})
    elapsed = time.perf_counter() - start

    assert len(findings) == 2
    assert elapsed < 0.18
