"""LLM-powered code analyzer."""

import json
from typing import Any, Optional
import structlog
from professor.core import Analyzer, Finding, FindingCategory, Location, Severity
from professor.llm import BaseLLMClient, LLMMessage

logger = structlog.get_logger()


class LLMAnalyzer(Analyzer):
    """Code analyzer using LLM for intelligent review."""

    def __init__(self, llm_client: BaseLLMClient, config: Optional[Any] = None) -> None:
        """Initialize LLM analyzer.

        Args:
            llm_client: LLM client instance
            config: Optional configuration
        """
        super().__init__(config)
        self.llm = llm_client
        self.name = "LLMAnalyzer"

    async def analyze(self, context: dict[str, Any]) -> list[Finding]:
        """Analyze code using LLM.

        Args:
            context: Must contain:
                - file_path: str
                - code: str
                - language: str (optional)
                - diff: str (optional)

        Returns:
            List of findings from LLM analysis

        Raises:
            AnalyzerError: If analysis fails
        """
        file_path = context.get("file_path", "unknown")
        code = context.get("code", "")
        diff = context.get("diff")
        language = context.get("language", "unknown")

        if not code and not diff:
            logger.warning("no_code_provided", file_path=file_path)
            return []

        # Build prompt
        prompt = self._build_review_prompt(file_path, code, diff, language)

        # Call LLM
        try:
            messages = [
                LLMMessage("system", self._get_system_prompt()),
                LLMMessage("user", prompt),
            ]

            response = await self.llm.complete(messages)

            logger.info(
                "llm_analysis_complete",
                file_path=file_path,
                tokens_used=response.tokens_used,
                cost=response.cost,
            )

            # Parse findings from response
            findings = self._parse_findings(response.content, file_path)
            return findings

        except Exception as e:
            logger.error("llm_analysis_failed", error=str(e), file_path=file_path)
            return []

    def supports(self, context: dict[str, Any]) -> bool:
        """Check if this analyzer supports the context.

        Args:
            context: Analysis context

        Returns:
            Always True - LLM can analyze any code
        """
        return "code" in context or "diff" in context

    def _get_system_prompt(self) -> str:
        """Get system prompt for LLM."""
        return """You are Professor, an expert code reviewer with superhuman attention to detail.

Your mission is to ensure the highest standards of code quality, security, and correctness.
You analyze code written by both humans and AI, catching subtle bugs, security vulnerabilities,
performance issues, and maintainability problems that others miss.

When reviewing code:
1. Focus on CRITICAL and HIGH severity issues (bugs, security, logic errors)
2. Be precise - only flag real issues, not stylistic preferences
3. Provide clear explanations and suggested fixes
4. Consider edge cases and potential failure modes
5. Think about security implications
6. Assess performance and scalability

Return findings in JSON format:
[
  {
    "severity": "critical|high|medium|low|info",
    "category": "bug|security|performance|maintainability|style|documentation|testing|architecture",
    "title": "Brief title",
    "message": "Detailed explanation",
    "line": 42,
    "suggestion": "How to fix it"
  }
]

If no issues found, return empty array: []"""

    def _build_review_prompt(
        self, file_path: str, code: str, diff: Optional[str], language: str
    ) -> str:
        """Build review prompt for LLM."""
        parts = [f"Review this {language} code from `{file_path}`:\n"]

        if diff:
            parts.append("CHANGES (diff):")
            parts.append("```diff")
            parts.append(diff)
            parts.append("```\n")

        if code:
            parts.append("FULL FILE:")
            parts.append(f"```{language}")
            parts.append(code)
            parts.append("```")

        parts.append(
            "\nAnalyze for bugs, security issues, logic errors, and quality problems."
        )
        parts.append("Return JSON array of findings (or [] if no issues).")

        return "\n".join(parts)

    def _parse_findings(self, response: str, file_path: str) -> list[Finding]:
        """Parse LLM response into Finding objects.

        Args:
            response: LLM response text
            file_path: File path for locations

        Returns:
            List of parsed findings
        """
        try:
            # Extract JSON from response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1

            if json_start == -1 or json_end == 0:
                logger.warning("no_json_in_response", response=response[:100])
                return []

            json_str = response[json_start:json_end]
            findings_data = json.loads(json_str)

            findings = []
            for idx, data in enumerate(findings_data):
                try:
                    location = Location(
                        file_path=file_path,
                        line_start=data.get("line", 1),
                        line_end=data.get("line_end"),
                    )

                    finding = Finding(
                        id=f"llm-{file_path}-{idx}",
                        severity=Severity(data["severity"].lower()),
                        category=FindingCategory(data["category"].lower()),
                        title=data["title"],
                        message=data["message"],
                        location=location,
                        suggestion=data.get("suggestion"),
                        analyzer=self.name,
                    )
                    findings.append(finding)

                except (KeyError, ValueError) as e:
                    logger.warning("invalid_finding_format", error=str(e), data=data)
                    continue

            logger.info("parsed_findings", count=len(findings), file_path=file_path)
            return findings

        except json.JSONDecodeError as e:
            logger.error("json_parse_error", error=str(e), response=response[:200])
            return []
        except Exception as e:
            logger.error("parse_error", error=str(e))
            return []
