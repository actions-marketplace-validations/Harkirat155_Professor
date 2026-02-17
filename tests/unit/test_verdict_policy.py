"""Tests for reviewer verdict policy and confidence scoring."""

from professor.core import Finding, FindingCategory, Location, Review, Severity
from professor.reviewer import PRReviewer


class DummyGitHubClient:
    pass


class DummyLLMClient:
    total_cost = 0.0


def _finding(fid: str, severity: Severity) -> Finding:
    return Finding(
        id=fid,
        severity=severity,
        category=FindingCategory.BUG,
        title=f"Finding {fid}",
        message="test",
        location=Location(file_path="a.py", line_start=1),
        analyzer="test",
    )


def test_verdict_rejects_on_critical():
    reviewer = PRReviewer(
        github_client=DummyGitHubClient(),
        llm_client=DummyLLMClient(),
        max_critical_issues=0,
        max_high_issues=1,
    )
    review = Review(id="r1")
    review.add_finding(_finding("f1", Severity.CRITICAL))
    approved, verdict, confidence = reviewer._evaluate_verdict(review)

    assert not approved
    assert verdict == "reject"
    assert confidence < 1.0


def test_verdict_approves_when_within_policy():
    reviewer = PRReviewer(
        github_client=DummyGitHubClient(),
        llm_client=DummyLLMClient(),
        max_critical_issues=0,
        max_high_issues=1,
    )
    review = Review(id="r2")
    review.add_finding(_finding("f1", Severity.HIGH))
    approved, verdict, confidence = reviewer._evaluate_verdict(review)

    assert approved
    assert verdict == "approve"
    assert 0.0 < confidence <= 1.0

