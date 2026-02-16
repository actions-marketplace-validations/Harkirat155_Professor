"""Core data models for Professor."""

from enum import Enum
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for code review findings."""

    CRITICAL = "critical"  # Security vulnerabilities, data loss, crashes
    HIGH = "high"  # Bugs, logic errors, major performance issues
    MEDIUM = "medium"  # Code quality, maintainability issues
    LOW = "low"  # Minor improvements, style suggestions
    INFO = "info"  # Informational notes, best practices


class FindingCategory(str, Enum):
    """Categories of code review findings."""

    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    ARCHITECTURE = "architecture"


class Location(BaseModel):
    """Location of a finding in code."""

    file_path: str = Field(..., description="Path to the file")
    line_start: int = Field(..., description="Starting line number", ge=1)
    line_end: Optional[int] = Field(None, description="Ending line number", ge=1)
    column_start: Optional[int] = Field(None, description="Starting column", ge=1)
    column_end: Optional[int] = Field(None, description="Ending column", ge=1)

    def __str__(self) -> str:
        """String representation of location."""
        if self.line_end and self.line_end != self.line_start:
            return f"{self.file_path}:{self.line_start}-{self.line_end}"
        return f"{self.file_path}:{self.line_start}"


class Finding(BaseModel):
    """A single code review finding."""

    id: str = Field(..., description="Unique identifier for the finding")
    severity: Severity = Field(..., description="Severity level")
    category: FindingCategory = Field(..., description="Category of the finding")
    title: str = Field(..., description="Brief title of the issue")
    message: str = Field(..., description="Detailed message explaining the issue")
    location: Location = Field(..., description="Location in code")
    suggestion: Optional[str] = Field(None, description="Suggested fix or improvement")
    code_snippet: Optional[str] = Field(None, description="Relevant code snippet")
    analyzer: str = Field(..., description="Name of the analyzer that generated this finding")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        """String representation of finding."""
        return f"[{self.severity.upper()}] {self.location}: {self.title}"


class ReviewStatus(str, Enum):
    """Status of a code review."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewSummary(BaseModel):
    """Summary statistics of a review."""

    total_findings: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    files_analyzed: int = 0
    lines_analyzed: int = 0

    @property
    def blocking_issues(self) -> int:
        """Number of blocking issues (critical + high)."""
        return self.critical + self.high

    @property
    def is_approved(self) -> bool:
        """Whether the review passes (no critical/high issues)."""
        return self.blocking_issues == 0


class Review(BaseModel):
    """A complete code review with all findings."""

    id: str = Field(..., description="Unique identifier for the review")
    status: ReviewStatus = Field(default=ReviewStatus.PENDING)
    findings: list[Finding] = Field(default_factory=list)
    summary: ReviewSummary = Field(default_factory=ReviewSummary)
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Review metadata (PR URL, commit SHA, etc.)"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the review and update summary."""
        self.findings.append(finding)
        self.summary.total_findings += 1

        # Update severity counts
        if finding.severity == Severity.CRITICAL:
            self.summary.critical += 1
        elif finding.severity == Severity.HIGH:
            self.summary.high += 1
        elif finding.severity == Severity.MEDIUM:
            self.summary.medium += 1
        elif finding.severity == Severity.LOW:
            self.summary.low += 1
        elif finding.severity == Severity.INFO:
            self.summary.info += 1

        self.updated_at = datetime.utcnow()

    def get_findings_by_severity(self, severity: Severity) -> list[Finding]:
        """Get all findings of a specific severity."""
        return [f for f in self.findings if f.severity == severity]

    def get_findings_by_category(self, category: FindingCategory) -> list[Finding]:
        """Get all findings of a specific category."""
        return [f for f in self.findings if f.category == category]

    def mark_completed(self) -> None:
        """Mark the review as completed."""
        self.status = ReviewStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_failed(self) -> None:
        """Mark the review as failed."""
        self.status = ReviewStatus.FAILED
        self.updated_at = datetime.utcnow()
