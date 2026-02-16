"""Security analyzer for detecting vulnerabilities and secrets."""

import re
from typing import Any, Optional
import structlog

from professor.core import Analyzer, Finding, FindingCategory, Location, Severity

logger = structlog.get_logger()


class SecurityAnalyzer(Analyzer):
    """Security analyzer for detecting common vulnerabilities."""

    # Common secret patterns
    SECRET_PATTERNS = {
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "GitHub Token": r"ghp_[0-9a-zA-Z]{36}",
        "Generic API Key": r"api[_-]?key['\"]?\s*[:=]\s*['\"]([0-9a-zA-Z\-_]{20,})['\"]",
        "Private Key": r"-----BEGIN (RSA |DSA )?PRIVATE KEY-----",
        "Generic Secret": r"secret['\"]?\s*[:=]\s*['\"]([^'\"]{20,})['\"]",
        "Password in Code": r"password['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
        "JWT Token": r"eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*",
    }

    # Security vulnerability patterns
    VULNERABILITY_PATTERNS = {
        "SQL Injection": {
            "pattern": r"(execute|cursor\.execute)\s*\([^)]*\.format\s*\(",
            "message": "Potential SQL injection vulnerability - user input in SQL query",
            "severity": Severity.CRITICAL,
        },
        "Command Injection": {
            "pattern": r"(os\.system|subprocess\.(call|run|Popen))\s*\(\s*.*\+.*\)",
            "message": "Potential command injection - user input in system command",
            "severity": Severity.CRITICAL,
        },
        "Hardcoded Password": {
            "pattern": r"password\s*=\s*['\"][^'\"]+['\"]",
            "message": "Hardcoded password in source code",
            "severity": Severity.HIGH,
        },
        "Unsafe Deserialization": {
            "pattern": r"pickle\.loads?\s*\(",
            "message": "Unsafe deserialization with pickle - potential code execution",
            "severity": Severity.HIGH,
        },
        "eval() Usage": {
            "pattern": r"\beval\s*\(",
            "message": "Use of eval() - potential code execution vulnerability",
            "severity": Severity.HIGH,
        },
        "Weak Hash": {
            "pattern": r"hashlib\.(md5|sha1)\s*\(",
            "message": "Use of weak hashing algorithm (MD5/SHA1)",
            "severity": Severity.MEDIUM,
        },
    }

    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize security analyzer."""
        super().__init__(config)
        self.name = "SecurityAnalyzer"

    async def analyze(self, context: dict[str, Any]) -> list[Finding]:
        """Analyze code for security issues.

        Args:
            context: Must contain:
                - file_path: str
                - code: str

        Returns:
            List of security findings
        """
        file_path = context.get("file_path", "unknown")
        code = context.get("code", "")

        if not code:
            return []

        findings = []

        # Check for secrets
        secret_findings = self._detect_secrets(file_path, code)
        findings.extend(secret_findings)

        # Check for vulnerabilities
        vuln_findings = self._detect_vulnerabilities(file_path, code)
        findings.extend(vuln_findings)

        logger.info(
            "security_analysis_complete",
            file_path=file_path,
            secrets=len(secret_findings),
            vulnerabilities=len(vuln_findings),
        )

        return findings

    def _detect_secrets(self, file_path: str, code: str) -> list[Finding]:
        """Detect potential secrets in code.

        Args:
            file_path: File path
            code: Code content

        Returns:
            List of findings for detected secrets
        """
        findings = []
        lines = code.split("\n")

        for secret_type, pattern in self.SECRET_PATTERNS.items():
            for line_num, line in enumerate(lines, 1):
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    # Skip comments and example values
                    if self._is_false_positive(line, match.group(0)):
                        continue

                    location = Location(
                        file_path=file_path,
                        line_start=line_num,
                        column_start=match.start() + 1,
                        column_end=match.end() + 1,
                    )

                    finding = Finding(
                        id=f"secret-{file_path}-{line_num}-{secret_type}",
                        severity=Severity.CRITICAL,
                        category=FindingCategory.SECURITY,
                        title=f"Potential {secret_type} exposed in code",
                        message=f"Found what appears to be a {secret_type}. "
                        "Secrets should never be committed to source code.",
                        location=location,
                        suggestion="Move secrets to environment variables or secret management system",
                        analyzer=self.name,
                        code_snippet=line.strip(),
                    )
                    findings.append(finding)

        return findings

    def _detect_vulnerabilities(self, file_path: str, code: str) -> list[Finding]:
        """Detect security vulnerabilities in code.

        Args:
            file_path: File path
            code: Code content

        Returns:
            List of vulnerability findings
        """
        findings = []
        lines = code.split("\n")

        for vuln_name, vuln_config in self.VULNERABILITY_PATTERNS.items():
            pattern = vuln_config["pattern"]

            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    # Skip comments
                    if line.strip().startswith("#") or line.strip().startswith("//"):
                        continue

                    location = Location(file_path=file_path, line_start=line_num)

                    finding = Finding(
                        id=f"vuln-{file_path}-{line_num}-{vuln_name.replace(' ', '-')}",
                        severity=vuln_config["severity"],
                        category=FindingCategory.SECURITY,
                        title=vuln_name,
                        message=vuln_config["message"],
                        location=location,
                        analyzer=self.name,
                        code_snippet=line.strip(),
                    )
                    findings.append(finding)

        return findings

    def _is_false_positive(self, line: str, match: str) -> bool:
        """Check if a secret detection is likely a false positive.

        Args:
            line: Full line of code
            match: Matched secret string

        Returns:
            True if likely false positive
        """
        # Skip comments
        if line.strip().startswith("#") or line.strip().startswith("//"):
            return True

        # Skip example/dummy values
        dummy_indicators = [
            "example",
            "dummy",
            "fake",
            "test",
            "sample",
            "placeholder",
            "your_",
            "xxx",
            "***",
        ]

        match_lower = match.lower()
        return any(indicator in match_lower for indicator in dummy_indicators)

    def supports(self, context: dict[str, Any]) -> bool:
        """Check if this analyzer supports the context.

        Args:
            context: Analysis context

        Returns:
            True if code is present
        """
        return "code" in context
