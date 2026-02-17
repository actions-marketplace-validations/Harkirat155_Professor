"""Tests for top-6 language analyzers."""

import pytest

from professor.analyzers.language_tool_analyzers import (
    CppStaticAnalyzer,
    ESLintAnalyzer,
    GoStaticAnalyzer,
    JavaStaticAnalyzer,
    RustStaticAnalyzer,
)
from professor.core import Severity


@pytest.mark.asyncio
async def test_eslint_analyzer_detects_eval():
    analyzer = ESLintAnalyzer()
    findings = await analyzer.analyze(
        {"file_path": "app.ts", "code": "const x = eval(userInput);"}
    )
    assert findings
    assert findings[0].severity == Severity.HIGH


@pytest.mark.asyncio
async def test_java_analyzer_detects_runtime_exec():
    analyzer = JavaStaticAnalyzer()
    findings = await analyzer.analyze(
        {"file_path": "Main.java", "code": "Runtime.getRuntime().exec(cmd);"}
    )
    assert findings


@pytest.mark.asyncio
async def test_go_analyzer_detects_sh_c():
    analyzer = GoStaticAnalyzer()
    findings = await analyzer.analyze(
        {"file_path": "main.go", "code": 'exec.Command("sh", "-c", userCmd)'}
    )
    assert findings


@pytest.mark.asyncio
async def test_rust_analyzer_detects_unsafe():
    analyzer = RustStaticAnalyzer()
    findings = await analyzer.analyze({"file_path": "lib.rs", "code": "unsafe { x(); }"})
    assert findings


@pytest.mark.asyncio
async def test_cpp_analyzer_detects_strcpy():
    analyzer = CppStaticAnalyzer()
    findings = await analyzer.analyze({"file_path": "main.cpp", "code": "strcpy(dst, src);"})
    assert findings
    assert findings[0].severity == Severity.CRITICAL

