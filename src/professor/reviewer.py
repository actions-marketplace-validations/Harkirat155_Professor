"""Pull Request reviewer orchestrator."""

import asyncio
from typing import Any, Optional
from dataclasses import dataclass
import structlog

from professor.core import Review, ReviewStatus, Severity
from professor.scm.github import GitHubClient, PullRequest, FileChange
from professor.analyzers.llm_analyzer import LLMAnalyzer
from professor.llm import BaseLLMClient
from professor.config import get_settings

logger = structlog.get_logger()


@dataclass
class ReviewResult:
    """Result of a PR review."""

    review: Review
    pr: PullRequest
    approved: bool
    blocking_issues: int
    total_findings: int
    cost: float


class PRReviewer:
    """Orchestrates pull request reviews."""

    def __init__(
        self,
        github_client: GitHubClient,
        llm_client: BaseLLMClient,
        max_files: int = 50,
        max_file_size_kb: int = 500,
        enable_static_analysis: bool = True,
        enable_security_scan: bool = True,
        enable_complexity_check: bool = True,
    ) -> None:
        """Initialize PR reviewer.

        Args:
            github_client: GitHub API client
            llm_client: LLM client for analysis
            max_files: Maximum files to review
            max_file_size_kb: Maximum file size in KB
            enable_static_analysis: Enable static analysis (ruff)
            enable_security_scan: Enable security scanning
            enable_complexity_check: Enable complexity checks
        """
        self.github = github_client
        self.llm = llm_client
        self.max_files = max_files
        self.max_file_size_kb = max_file_size_kb

        # Initialize analyzers
        from professor.analyzers.llm_analyzer import LLMAnalyzer
        from professor.analyzers.security_analyzer import SecurityAnalyzer
        from professor.analyzers.complexity_analyzer import ComplexityAnalyzer
        from professor.core import CompositeAnalyzer

        analyzers = [LLMAnalyzer(llm_client)]

        if enable_security_scan:
            analyzers.append(SecurityAnalyzer())

        if enable_complexity_check:
            analyzers.append(ComplexityAnalyzer())

        if enable_static_analysis:
            try:
                from professor.analyzers.ruff_analyzer import RuffAnalyzer
                analyzers.append(RuffAnalyzer())
            except Exception:
                logger.warning("ruff_analyzer_disabled", reason="ruff not available")

        self.analyzer = CompositeAnalyzer(analyzers)

        logger.info(
            "pr_reviewer_initialized",
            max_files=max_files,
            max_file_size_kb=max_file_size_kb,
            analyzers=len(analyzers),
        )

    async def review_pull_request(
        self, owner: str, repo: str, pr_number: int
    ) -> ReviewResult:
        """Review a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number

        Returns:
            ReviewResult with findings and metadata

        Raises:
            ReviewError: If review fails
        """
        logger.info(
            "starting_pr_review", owner=owner, repo=repo, pr_number=pr_number
        )

        try:
            # Create review
            review = Review(
                id=f"{owner}/{repo}/pull/{pr_number}",
                metadata={
                    "owner": owner,
                    "repo": repo,
                    "pr_number": pr_number,
                },
            )
            review.status = ReviewStatus.IN_PROGRESS

            # Fetch PR data
            pr = await self.github.get_pull_request(owner, repo, pr_number)
            file_changes = await self.github.get_file_changes(owner, repo, pr_number)

            logger.info(
                "pr_data_fetched",
                pr_number=pr_number,
                files=len(file_changes),
                additions=pr.additions,
                deletions=pr.deletions,
            )

            # Filter files
            reviewable_files = self._filter_files(file_changes)

            if len(reviewable_files) > self.max_files:
                logger.warning(
                    "too_many_files",
                    total=len(reviewable_files),
                    max=self.max_files,
                )
                reviewable_files = reviewable_files[: self.max_files]

            # Analyze each file
            total_cost = 0.0
            for file_change in reviewable_files:
                try:
                    findings = await self._analyze_file(
                        owner, repo, pr.head_branch, file_change
                    )

                    for finding in findings:
                        review.add_finding(finding)

                    # Track cost
                    total_cost += getattr(self.llm, "total_cost", 0.0)

                    logger.info(
                        "file_analyzed",
                        file=file_change.filename,
                        findings=len(findings),
                    )

                except Exception as e:
                    logger.error(
                        "file_analysis_failed",
                        file=file_change.filename,
                        error=str(e),
                    )
                    continue

            # Update review metadata
            review.summary.files_analyzed = len(reviewable_files)
            review.mark_completed()

            result = ReviewResult(
                review=review,
                pr=pr,
                approved=review.summary.is_approved,
                blocking_issues=review.summary.blocking_issues,
                total_findings=review.summary.total_findings,
                cost=total_cost,
            )

            logger.info(
                "pr_review_complete",
                pr_number=pr_number,
                findings=result.total_findings,
                approved=result.approved,
                cost=f"${result.cost:.4f}",
            )

            return result

        except Exception as e:
            logger.error("pr_review_failed", error=str(e))
            raise ReviewError(f"Failed to review PR: {e}") from e

    async def _analyze_file(
        self, owner: str, repo: str, ref: str, file_change: FileChange
    ) -> list[Any]:
        """Analyze a single file.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git ref
            file_change: File change to analyze

        Returns:
            List of findings
        """
        # Get file content
        try:
            content = await self.github.get_file_content(
                owner, repo, file_change.filename, ref
            )
        except Exception as e:
            logger.warning(
                "file_content_fetch_failed",
                file=file_change.filename,
                error=str(e),
            )
            content = ""

        # Prepare context
        context = {
            "file_path": file_change.filename,
            "code": content,
            "diff": file_change.patch,
            "language": self._detect_language(file_change.filename),
            "status": file_change.status,
        }

        # Run analyzer
        findings = await self.analyzer.analyze(context)
        return findings

    def _filter_files(self, file_changes: list[FileChange]) -> list[FileChange]:
        """Filter files that should be reviewed.

        Args:
            file_changes: All file changes

        Returns:
            Filtered list of files to review
        """
        reviewable = []

        for file_change in file_changes:
            # Skip deleted files
            if file_change.status == "removed":
                continue

            # Skip files that are too large
            if file_change.changes > (self.max_file_size_kb * 10):
                logger.info("skipping_large_file", file=file_change.filename)
                continue

            # Skip binary files
            if self._is_binary_file(file_change.filename):
                continue

            # Skip generated files
            if self._is_generated_file(file_change.filename):
                continue

            reviewable.append(file_change)

        return reviewable

    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename.

        Args:
            filename: File name

        Returns:
            Language name
        """
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".kt": "kotlin",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".cs": "csharp",
            ".scala": "scala",
        }

        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang

        return "unknown"

    def _is_binary_file(self, filename: str) -> bool:
        """Check if file is binary.

        Args:
            filename: File name

        Returns:
            True if binary
        """
        binary_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".wasm",
        }

        return any(filename.endswith(ext) for ext in binary_extensions)

    def _is_generated_file(self, filename: str) -> bool:
        """Check if file is generated.

        Args:
            filename: File name

        Returns:
            True if generated
        """
        patterns = [
            ".generated.",
            ".min.",
            "package-lock.json",
            "yarn.lock",
            "Pipfile.lock",
            "poetry.lock",
            "go.sum",
        ]

        return any(pattern in filename for pattern in patterns)


class ReviewError(Exception):
    """Raised when review fails."""

    pass
