"""Language-specific analyzers for top-6 languages."""

import re
from typing import Any, Optional

from professor.core import Analyzer, Finding, FindingCategory, Location, Severity


class _RegexLanguageAnalyzer(Analyzer):
    """Base regex analyzer for language-specific risk patterns."""

    supported_extensions: tuple[str, ...] = ()
    rules: list[dict[str, Any]] = []

    def __init__(self, config: Optional[Any] = None) -> None:
        super().__init__(config)
        self.name = self.__class__.__name__

    async def analyze(self, context: dict[str, Any]) -> list[Finding]:
        code = context.get("code", "")
        file_path = context.get("file_path", "")
        if not self.supports(context):
            return []

        findings: list[Finding] = []
        lines = code.split("\n")
        for index, line in enumerate(lines, start=1):
            if self._is_comment_line(line):
                continue
            for rule in self.rules:
                if re.search(rule["pattern"], line):
                    findings.append(
                        Finding(
                            id=f"{self.name.lower()}-{file_path}-{index}-{rule['id']}",
                            severity=rule["severity"],
                            category=rule["category"],
                            title=rule["title"],
                            message=rule["message"],
                            location=Location(file_path=file_path, line_start=index),
                            suggestion=rule.get("suggestion"),
                            analyzer=self.name,
                            code_snippet=line.strip(),
                        )
                    )
        return findings

    def supports(self, context: dict[str, Any]) -> bool:
        file_path = context.get("file_path", "").lower()
        return bool(context.get("code")) and file_path.endswith(self.supported_extensions)

    def _is_comment_line(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*")


class ESLintAnalyzer(_RegexLanguageAnalyzer):
    """JS/TS safety analyzer compatible with PR-file-content scanning."""

    supported_extensions = (".js", ".jsx", ".ts", ".tsx")
    rules = [
        {
            "id": "eval",
            "pattern": r"\beval\s*\(",
            "severity": Severity.HIGH,
            "category": FindingCategory.SECURITY,
            "title": "Dangerous eval() usage",
            "message": "eval() can execute attacker-controlled code and should be avoided.",
            "suggestion": "Use safe parsers or explicit function dispatch.",
        },
        {
            "id": "new-function",
            "pattern": r"\bnew\s+Function\s*\(",
            "severity": Severity.HIGH,
            "category": FindingCategory.SECURITY,
            "title": "Dynamic Function constructor usage",
            "message": "new Function() has similar risks to eval() and weakens security.",
            "suggestion": "Avoid dynamic code execution.",
        },
        {
            "id": "innerhtml",
            "pattern": r"\.innerHTML\s*=",
            "severity": Severity.MEDIUM,
            "category": FindingCategory.SECURITY,
            "title": "Potential DOM XSS sink",
            "message": "Direct innerHTML assignment can introduce XSS if input is not sanitized.",
            "suggestion": "Use textContent or sanitize HTML before assignment.",
        },
    ]


class JavaStaticAnalyzer(_RegexLanguageAnalyzer):
    supported_extensions = (".java",)
    rules = [
        {
            "id": "runtime-exec",
            "pattern": r"Runtime\.getRuntime\(\)\.exec\s*\(",
            "severity": Severity.HIGH,
            "category": FindingCategory.SECURITY,
            "title": "Command execution surface",
            "message": "Runtime.exec can enable command injection with untrusted input.",
            "suggestion": "Use ProcessBuilder with strict argument handling and validation.",
        },
        {
            "id": "statement-execute",
            "pattern": r"\bStatement\b.*\bexecute(Query|Update)?\s*\(",
            "severity": Severity.HIGH,
            "category": FindingCategory.SECURITY,
            "title": "Raw SQL execution with Statement",
            "message": "Raw Statement execution increases SQL injection risk.",
            "suggestion": "Use PreparedStatement with bound parameters.",
        },
    ]


class GoStaticAnalyzer(_RegexLanguageAnalyzer):
    supported_extensions = (".go",)
    rules = [
        {
            "id": "shell-command",
            "pattern": r"exec\.Command\s*\(\s*\"sh\"\s*,\s*\"-c\"",
            "severity": Severity.HIGH,
            "category": FindingCategory.SECURITY,
            "title": "Shell command execution",
            "message": "Using 'sh -c' can introduce command injection paths.",
            "suggestion": "Pass command and args directly without shell expansion.",
        },
        {
            "id": "panic-err",
            "pattern": r"panic\s*\(\s*err\s*\)",
            "severity": Severity.MEDIUM,
            "category": FindingCategory.MAINTAINABILITY,
            "title": "panic(err) in runtime path",
            "message": "panic(err) can crash services and reduce fault tolerance.",
            "suggestion": "Return and handle errors explicitly.",
        },
    ]


class RustStaticAnalyzer(_RegexLanguageAnalyzer):
    supported_extensions = (".rs",)
    rules = [
        {
            "id": "unsafe-block",
            "pattern": r"\bunsafe\s*\{",
            "severity": Severity.MEDIUM,
            "category": FindingCategory.SECURITY,
            "title": "Unsafe block present",
            "message": "Unsafe blocks require strict justification and invariants.",
            "suggestion": "Document safety invariants and minimize unsafe scope.",
        },
        {
            "id": "unwrap",
            "pattern": r"\.unwrap\s*\(",
            "severity": Severity.MEDIUM,
            "category": FindingCategory.MAINTAINABILITY,
            "title": "Unchecked unwrap()",
            "message": "unwrap() can panic in production paths.",
            "suggestion": "Use proper error handling with Result propagation.",
        },
    ]


class CppStaticAnalyzer(_RegexLanguageAnalyzer):
    supported_extensions = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp")
    rules = [
        {
            "id": "strcpy",
            "pattern": r"\bstrcpy\s*\(",
            "severity": Severity.CRITICAL,
            "category": FindingCategory.SECURITY,
            "title": "Unsafe strcpy usage",
            "message": "strcpy can cause buffer overflows and memory corruption.",
            "suggestion": "Use bounded copy APIs and explicit size checks.",
        },
        {
            "id": "sprintf",
            "pattern": r"\bsprintf\s*\(",
            "severity": Severity.HIGH,
            "category": FindingCategory.SECURITY,
            "title": "Unbounded sprintf usage",
            "message": "sprintf is unbounded and can overflow output buffers.",
            "suggestion": "Use snprintf with strict destination length.",
        },
        {
            "id": "system-call",
            "pattern": r"\bsystem\s*\(",
            "severity": Severity.HIGH,
            "category": FindingCategory.SECURITY,
            "title": "System shell execution",
            "message": "system() can be abused for command injection.",
            "suggestion": "Use safer process execution APIs with validated arguments.",
        },
    ]

