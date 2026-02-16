"""Tests for core models."""

import pytest
from datetime import datetime
from professor.core.models import (
    Finding,
    FindingCategory,
    Location,
    Review,
    ReviewStatus,
    Severity,
)


def test_location_string_representation():
    """Test location string formatting."""
    loc = Location(file_path="src/main.py", line_start=10)
    assert str(loc) == "src/main.py:10"
    
    loc_range = Location(file_path="src/main.py", line_start=10, line_end=15)
    assert str(loc_range) == "src/main.py:10-15"


def test_finding_creation():
    """Test finding creation and attributes."""
    location = Location(file_path="src/main.py", line_start=10)
    finding = Finding(
        id="test-1",
        severity=Severity.HIGH,
        category=FindingCategory.BUG,
        title="Null pointer exception",
        message="Variable may be None",
        location=location,
        analyzer="TestAnalyzer",
    )
    
    assert finding.severity == Severity.HIGH
    assert finding.category == FindingCategory.BUG
    assert "Null pointer" in finding.title
    assert finding.analyzer == "TestAnalyzer"


def test_review_add_finding():
    """Test adding findings to review."""
    review = Review(id="review-1")
    location = Location(file_path="src/main.py", line_start=10)
    
    # Add critical finding
    critical_finding = Finding(
        id="f1",
        severity=Severity.CRITICAL,
        category=FindingCategory.SECURITY,
        title="SQL Injection",
        message="Unsafe SQL query",
        location=location,
        analyzer="SecurityAnalyzer",
    )
    review.add_finding(critical_finding)
    
    assert review.summary.total_findings == 1
    assert review.summary.critical == 1
    assert review.summary.blocking_issues == 1
    assert not review.summary.is_approved
    
    # Add high severity finding
    high_finding = Finding(
        id="f2",
        severity=Severity.HIGH,
        category=FindingCategory.BUG,
        title="Logic error",
        message="Incorrect condition",
        location=location,
        analyzer="LLMAnalyzer",
    )
    review.add_finding(high_finding)
    
    assert review.summary.total_findings == 2
    assert review.summary.high == 1
    assert review.summary.blocking_issues == 2


def test_review_filtering():
    """Test filtering findings by severity and category."""
    review = Review(id="review-1")
    location = Location(file_path="src/main.py", line_start=10)
    
    # Add multiple findings
    findings = [
        Finding(
            id="f1",
            severity=Severity.CRITICAL,
            category=FindingCategory.SECURITY,
            title="Security issue",
            message="Vulnerability found",
            location=location,
            analyzer="SecurityAnalyzer",
        ),
        Finding(
            id="f2",
            severity=Severity.HIGH,
            category=FindingCategory.BUG,
            title="Bug",
            message="Logic error",
            location=location,
            analyzer="LLMAnalyzer",
        ),
        Finding(
            id="f3",
            severity=Severity.LOW,
            category=FindingCategory.STYLE,
            title="Style",
            message="Formatting issue",
            location=location,
            analyzer="StyleAnalyzer",
        ),
    ]
    
    for finding in findings:
        review.add_finding(finding)
    
    # Test severity filtering
    critical_findings = review.get_findings_by_severity(Severity.CRITICAL)
    assert len(critical_findings) == 1
    assert critical_findings[0].id == "f1"
    
    # Test category filtering
    security_findings = review.get_findings_by_category(FindingCategory.SECURITY)
    assert len(security_findings) == 1
    assert security_findings[0].title == "Security issue"


def test_review_status_transitions():
    """Test review status changes."""
    review = Review(id="review-1")
    assert review.status == ReviewStatus.PENDING
    assert review.completed_at is None
    
    review.mark_completed()
    assert review.status == ReviewStatus.COMPLETED
    assert review.completed_at is not None
    
    review2 = Review(id="review-2")
    review2.mark_failed()
    assert review2.status == ReviewStatus.FAILED


def test_review_approval_logic():
    """Test review approval based on findings."""
    review = Review(id="review-1")
    location = Location(file_path="src/main.py", line_start=10)
    
    # Review with only low/info findings should be approved
    low_finding = Finding(
        id="f1",
        severity=Severity.LOW,
        category=FindingCategory.STYLE,
        title="Style issue",
        message="Minor formatting",
        location=location,
        analyzer="StyleAnalyzer",
    )
    review.add_finding(low_finding)
    assert review.summary.is_approved
    
    # Adding high severity should block approval
    high_finding = Finding(
        id="f2",
        severity=Severity.HIGH,
        category=FindingCategory.BUG,
        title="Bug",
        message="Logic error",
        location=location,
        analyzer="LLMAnalyzer",
    )
    review.add_finding(high_finding)
    assert not review.summary.is_approved
