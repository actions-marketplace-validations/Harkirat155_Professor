"""Tests for complexity analyzer."""

import pytest
from professor.analyzers.complexity_analyzer import ComplexityAnalyzer
from professor.core.models import Severity, FindingCategory


@pytest.mark.asyncio
async def test_high_complexity():
    """Test detection of high complexity function."""
    analyzer = ComplexityAnalyzer(max_complexity=5)

    code = """
def complex_function(x):
    if x > 0:
        if x < 10:
            if x % 2 == 0:
                if x > 5:
                    if x < 8:
                        return "complex"
    return "simple"
"""

    context = {"file_path": "test.py", "code": code}
    findings = await analyzer.analyze(context)

    complexity_findings = [f for f in findings if "complexity" in f.title.lower()]
    assert len(complexity_findings) > 0
    assert complexity_findings[0].category == FindingCategory.MAINTAINABILITY


@pytest.mark.asyncio
async def test_long_function():
    """Test detection of long function."""
    analyzer = ComplexityAnalyzer(max_function_lines=10)

    # Generate a function with many lines
    lines = ["def long_function():"]
    for i in range(20):
        lines.append(f"    x{i} = {i}")
    lines.append("    return x0")

    code = "\n".join(lines)

    context = {"file_path": "test.py", "code": code}
    findings = await analyzer.analyze(context)

    length_findings = [f for f in findings if "Long function" in f.title]
    assert len(length_findings) > 0


@pytest.mark.asyncio
async def test_too_many_parameters():
    """Test detection of too many parameters."""
    analyzer = ComplexityAnalyzer(max_params=3)

    code = """
def many_params(a, b, c, d, e, f, g, h):
    return a + b + c + d + e + f + g + h
"""

    context = {"file_path": "test.py", "code": code}
    findings = await analyzer.analyze(context)

    param_findings = [f for f in findings if "parameter" in f.title.lower()]
    assert len(param_findings) > 0


@pytest.mark.asyncio
async def test_large_class():
    """Test detection of large class."""
    analyzer = ComplexityAnalyzer()

    # Generate a class with many methods
    lines = ["class LargeClass:"]
    for i in range(25):
        lines.append(f"    def method_{i}(self):")
        lines.append(f"        return {i}")

    code = "\n".join(lines)

    context = {"file_path": "test.py", "code": code}
    findings = await analyzer.analyze(context)

    class_findings = [f for f in findings if "Large class" in f.title]
    assert len(class_findings) > 0
    assert class_findings[0].category == FindingCategory.ARCHITECTURE


@pytest.mark.asyncio
async def test_simple_function():
    """Test that simple functions don't trigger findings."""
    analyzer = ComplexityAnalyzer()

    code = """
def simple_function(x, y):
    return x + y
"""

    context = {"file_path": "test.py", "code": code}
    findings = await analyzer.analyze(context)

    assert len(findings) == 0


@pytest.mark.asyncio
async def test_supports():
    """Test supports method."""
    analyzer = ComplexityAnalyzer()

    assert analyzer.supports({"file_path": "test.py", "code": "x = 1"})
    assert not analyzer.supports({"file_path": "test.js", "code": "var x = 1"})
    assert not analyzer.supports({"file_path": "test.py"})
