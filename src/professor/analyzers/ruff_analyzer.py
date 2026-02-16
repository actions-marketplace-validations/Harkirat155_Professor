"""Static code analysis using Ruff for Python."""

import subprocess
import json
from typing import Any, Optional
import structlog

from professor.core import Analyzer, Finding, FindingCategory, Location, Severity

logger = structlog.get_logger()


class RuffAnalyzer(Analyzer):
    """Python code analyzer using Ruff linter."""

    SEVERITY_MAP = {
        "E": Severity.HIGH,      # Error
        "F": Severity.HIGH,      # Pyflakes
        "W": Severity.MEDIUM,    # Warning
        "C": Severity.LOW,       # Convention
        "R": Severity.LOW,       # Refactor
        "S": Severity.CRITICAL,  # Security (bandit)
        "B": Severity.HIGH,      # Bugbear
        "I": Severity.INFO,      # Import
    }

    CATEGORY_MAP = {
        "E": FindingCategory.STYLE,
        "F": FindingCategory.BUG,
        "W": FindingCategory.MAINTAINABILITY,
        "C": FindingCategory.MAINTAINABILITY,
        "R": FindingCategory.MAINTAINABILITY,
        "S": FindingCategory.SECURITY,
        "B": FindingCategory.BUG,
        "I": FindingCategory.STYLE,
    }

    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize Ruff analyzer."""
        super().__init__(config)
        self.name = "RuffAnalyzer"

    async def analyze(self, context: dict[str, Any]) -> list[Finding]:
        """Analyze Python code using Ruff.

        Args:
            context: Must contain:
                - file_path: str
                - code: str

        Returns:
            List of findings from Ruff
        """
        file_path = context.get("file_path", "unknown.py")
        code = context.get("code", "")

        if not code:
            return []

        # Check if this is Python
        if not file_path.endswith(".py"):
            return []

        try:
            # Run ruff on the code
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", "-"],
                input=code.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if result.returncode == 0:
                # No issues found
                logger.info("ruff_analysis_clean", file_path=file_path)
                return []

            # Parse JSON output
            try:
                issues = json.loads(result.stdout.decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning("ruff_json_parse_failed", output=result.stdout[:200])
                return []

            # Convert to findings
            findings = []
            for issue in issues:
                try:
                    code_prefix = issue.get("code", "E")[0]
                    severity = self.SEVERITY_MAP.get(code_prefix, Severity.MEDIUM)
                    category = self.CATEGORY_MAP.get(code_prefix, FindingCategory.STYLE)

                    location = Location(
                        file_path=file_path,
                        line_start=issue.get("location", {}).get("row", 1),
                        column_start=issue.get("location", {}).get("column", 1),
                    )

                    finding = Finding(
                        id=f"ruff-{file_path}-{issue.get('code')}",
                        severity=severity,
                        category=category,
                        title=f"{issue.get('code')}: {issue.get('message', 'Unknown issue')}",
                        message=issue.get("message", ""),
                        location=location,
                        suggestion=issue.get("fix", {}).get("message") if issue.get("fix") else None,
                        analyzer=self.name,
                        metadata={"rule": issue.get("code"), "url": issue.get("url")},
                    )
                    findings.append(finding)

                except (KeyError, ValueError) as e:
                    logger.warning("ruff_finding_parse_failed", error=str(e), issue=issue)
                    continue

            logger.info("ruff_analysis_complete", file_path=file_path, findings=len(findings))
            return findings

        except subprocess.TimeoutExpired:
            logger.error("ruff_timeout", file_path=file_path)
            return []
        except FileNotFoundError:
            logger.warning("ruff_not_installed")
            return []
        except Exception as e:
            logger.error("ruff_analysis_failed", error=str(e), file_path=file_path)
            return []

    def supports(self, context: dict[str, Any]) -> bool:
        """Check if this analyzer supports the context.

        Args:
            context: Analysis context

        Returns:
            True if Python file
        """
        file_path = context.get("file_path", "")
        return file_path.endswith(".py") and "code" in context
