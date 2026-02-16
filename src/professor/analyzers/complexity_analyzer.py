"""Code complexity analyzer."""

import ast
from typing import Any, Optional
import structlog

from professor.core import Analyzer, Finding, FindingCategory, Location, Severity

logger = structlog.get_logger()


class ComplexityAnalyzer(Analyzer):
    """Analyzes code complexity metrics."""

    def __init__(
        self,
        max_complexity: int = 15,
        max_function_lines: int = 100,
        max_params: int = 7,
        config: Optional[Any] = None,
    ) -> None:
        """Initialize complexity analyzer.

        Args:
            max_complexity: Maximum cyclomatic complexity
            max_function_lines: Maximum lines per function
            max_params: Maximum parameters per function
            config: Optional configuration
        """
        super().__init__(config)
        self.name = "ComplexityAnalyzer"
        self.max_complexity = max_complexity
        self.max_function_lines = max_function_lines
        self.max_params = max_params

    async def analyze(self, context: dict[str, Any]) -> list[Finding]:
        """Analyze code complexity.

        Args:
            context: Must contain:
                - file_path: str
                - code: str

        Returns:
            List of complexity findings
        """
        file_path = context.get("file_path", "unknown")
        code = context.get("code", "")

        # Only analyze Python files
        if not file_path.endswith(".py") or not code:
            return []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.warning("ast_parse_failed", file_path=file_path, error=str(e))
            return []

        findings = []

        # Analyze each function
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_findings = self._analyze_function(node, file_path, code)
                findings.extend(func_findings)

            # Check for nested complexity
            if isinstance(node, ast.ClassDef):
                class_findings = self._analyze_class(node, file_path)
                findings.extend(class_findings)

        logger.info("complexity_analysis_complete", file_path=file_path, findings=len(findings))
        return findings

    def _analyze_function(
        self, node: ast.FunctionDef, file_path: str, code: str
    ) -> list[Finding]:
        """Analyze a single function.

        Args:
            node: AST function node
            file_path: File path
            code: Full code

        Returns:
            List of findings for this function
        """
        findings = []

        # Calculate cyclomatic complexity
        complexity = self._calculate_complexity(node)
        if complexity > self.max_complexity:
            location = Location(file_path=file_path, line_start=node.lineno)

            finding = Finding(
                id=f"complexity-{file_path}-{node.lineno}-cyclomatic",
                severity=Severity.MEDIUM if complexity <= 20 else Severity.HIGH,
                category=FindingCategory.MAINTAINABILITY,
                title=f"High cyclomatic complexity: {complexity}",
                message=f"Function '{node.name}' has cyclomatic complexity of {complexity} "
                f"(max {self.max_complexity}). Consider breaking it into smaller functions.",
                location=location,
                suggestion="Refactor into smaller, focused functions",
                analyzer=self.name,
                metadata={"complexity": complexity, "function": node.name},
            )
            findings.append(finding)

        # Check function length
        func_lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0
        if func_lines > self.max_function_lines:
            location = Location(
                file_path=file_path, line_start=node.lineno, line_end=node.end_lineno
            )

            finding = Finding(
                id=f"complexity-{file_path}-{node.lineno}-length",
                severity=Severity.LOW,
                category=FindingCategory.MAINTAINABILITY,
                title=f"Long function: {func_lines} lines",
                message=f"Function '{node.name}' is {func_lines} lines long "
                f"(max {self.max_function_lines}). Long functions are harder to understand and test.",
                location=location,
                suggestion="Break into smaller, focused functions",
                analyzer=self.name,
                metadata={"lines": func_lines, "function": node.name},
            )
            findings.append(finding)

        # Check parameter count
        param_count = len(node.args.args)
        if param_count > self.max_params:
            location = Location(file_path=file_path, line_start=node.lineno)

            finding = Finding(
                id=f"complexity-{file_path}-{node.lineno}-params",
                severity=Severity.LOW,
                category=FindingCategory.MAINTAINABILITY,
                title=f"Too many parameters: {param_count}",
                message=f"Function '{node.name}' has {param_count} parameters "
                f"(max {self.max_params}). Consider using a configuration object or builder pattern.",
                location=location,
                suggestion="Use a configuration object or dataclass",
                analyzer=self.name,
                metadata={"params": param_count, "function": node.name},
            )
            findings.append(finding)

        return findings

    def _analyze_class(self, node: ast.ClassDef, file_path: str) -> list[Finding]:
        """Analyze a class.

        Args:
            node: AST class node
            file_path: File path

        Returns:
            List of findings for this class
        """
        findings = []

        # Count methods
        methods = [
            n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        if len(methods) > 20:
            location = Location(file_path=file_path, line_start=node.lineno)

            finding = Finding(
                id=f"complexity-{file_path}-{node.lineno}-class-methods",
                severity=Severity.MEDIUM,
                category=FindingCategory.ARCHITECTURE,
                title=f"Large class: {len(methods)} methods",
                message=f"Class '{node.name}' has {len(methods)} methods. "
                "This may violate Single Responsibility Principle.",
                location=location,
                suggestion="Consider splitting into multiple classes",
                analyzer=self.name,
                metadata={"methods": len(methods), "class": node.name},
            )
            findings.append(finding)

        return findings

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function.

        Args:
            node: Function AST node

        Returns:
            Cyclomatic complexity
        """
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Each decision point adds 1
            if isinstance(
                child,
                (
                    ast.If,
                    ast.While,
                    ast.For,
                    ast.AsyncFor,
                    ast.ExceptHandler,
                    ast.With,
                    ast.AsyncWith,
                ),
            ):
                complexity += 1
            # Logical operators
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            # Comprehensions
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                complexity += len(child.generators)

        return complexity

    def supports(self, context: dict[str, Any]) -> bool:
        """Check if this analyzer supports the context.

        Args:
            context: Analysis context

        Returns:
            True if Python file
        """
        file_path = context.get("file_path", "")
        return file_path.endswith(".py") and "code" in context
