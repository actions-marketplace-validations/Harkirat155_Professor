"""Tests for security analyzer."""

import pytest
from professor.analyzers.security_analyzer import SecurityAnalyzer
from professor.core.models import Severity, FindingCategory


@pytest.mark.asyncio
async def test_detect_secrets():
    """Test secret detection."""
    analyzer = SecurityAnalyzer()

    code = """
# This file contains secrets (for testing)
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
github_token = "ghp_1234567890abcdefghijklmnopqrstuv"
api_key = "sk-proj-very_long_api_key_here_1234567890abcdefghij"
"""

    context = {"file_path": "test.py", "code": code}
    findings = await analyzer.analyze(context)

    # Should detect secrets
    assert len(findings) > 0
    assert all(f.severity == Severity.CRITICAL for f in findings)
    assert all(f.category == FindingCategory.SECURITY for f in findings)


@pytest.mark.asyncio
async def test_detect_sql_injection():
    """Test SQL injection detection."""
    analyzer = SecurityAnalyzer()

    code = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = {}".format(user_id)
    execute(query)
"""

    context = {"file_path": "database.py", "code": code}
    findings = await analyzer.analyze(context)

    # Should detect SQL injection
    sql_findings = [f for f in findings if "SQL" in f.title or "injection" in f.message.lower()]
    assert len(sql_findings) > 0
    assert sql_findings[0].severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_detect_eval_usage():
    """Test eval() detection."""
    analyzer = SecurityAnalyzer()

    code = """
def process_input(user_input):
    result = eval(user_input)  # Dangerous!
    return result
"""

    context = {"file_path": "processor.py", "code": code}
    findings = await analyzer.analyze(context)

    eval_findings = [f for f in findings if "eval" in f.title.lower()]
    assert len(eval_findings) > 0
    assert eval_findings[0].severity == Severity.HIGH


@pytest.mark.asyncio
async def test_ignore_comments():
    """Test that secrets in comments are ignored."""
    analyzer = SecurityAnalyzer()

    code = """
# Example: api_key = "sk-example_key_here_not_real_12345678901234567890"
# This is just a comment with AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
"""

    context = {"file_path": "test.py", "code": code}
    findings = await analyzer.analyze(context)

    # Comments should be ignored
    assert len(findings) == 0


@pytest.mark.asyncio
async def test_supports():
    """Test supports method."""
    analyzer = SecurityAnalyzer()

    assert analyzer.supports({"code": "some code"})
    assert not analyzer.supports({"no_code": "here"})
