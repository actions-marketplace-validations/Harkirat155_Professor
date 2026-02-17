"""Benchmark harness for labeled PR evaluation loops."""

from dataclasses import dataclass
from collections import defaultdict
import json
from pathlib import Path
from statistics import fmean
from typing import Any

from professor.core import FindingCategory, Severity


DEFAULT_LANGUAGE_TARGETS: dict[str, int] = {
    "python": 10,
    "javascript": 8,
    "typescript": 8,
    "java": 8,
    "go": 8,
    "rust": 4,
    "cpp": 4,
}


@dataclass(frozen=True)
class LabeledFinding:
    """Normalized finding used for benchmark labels and predictions."""

    signature: str
    severity: Severity
    category: FindingCategory

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "LabeledFinding":
        """Build finding from JSON-like mapping."""
        return cls(
            signature=data["signature"],
            severity=Severity(data["severity"].lower()),
            category=FindingCategory(data["category"].lower()),
        )


@dataclass
class BenchmarkCase:
    """Single labeled PR case for benchmark evaluation."""

    case_id: str
    language: str
    expected_findings: list[LabeledFinding]
    predicted_findings: list[LabeledFinding]
    expected_blocked: bool | None = None
    predicted_blocked: bool | None = None
    repo_family: str = "unknown"
    source_url: str = ""
    notes: str = ""


@dataclass
class BenchmarkDataset:
    """Collection of benchmark cases."""

    cases: list[BenchmarkCase]


@dataclass
class CaseMetrics:
    """Evaluation metrics for a benchmark case."""

    case_id: str
    language: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    severe_recall: float
    verdict_correct: bool


@dataclass
class BenchmarkMetrics:
    """Aggregate benchmark report."""

    case_metrics: list[CaseMetrics]
    total_cases: int
    mean_precision: float
    mean_recall: float
    mean_f1: float
    mean_severe_recall: float
    verdict_accuracy: float


@dataclass
class Scorecard:
    """Grouped benchmark scorecard."""

    group: str
    cases: int
    mean_precision: float
    mean_recall: float
    mean_f1: float
    severe_recall: float
    verdict_accuracy: float


@dataclass
class DatasetValidation:
    """Validation status for benchmark corpus coverage."""

    valid: bool
    issues: list[str]
    total_cases: int
    language_counts: dict[str, int]


@dataclass
class CurationStatus:
    """Curation completeness status for benchmark corpus."""

    valid: bool
    total_cases: int
    curated_cases: int
    completion_ratio: float
    by_language: dict[str, float]
    pending_case_ids: list[str]
    issues: list[str]


@dataclass(frozen=True)
class ReleaseGateThresholds:
    """Thresholds required to pass benchmark release gate."""

    min_mean_precision: float = 0.9
    min_mean_recall: float = 0.85
    min_mean_f1: float = 0.87
    min_severe_recall: float = 0.95
    min_verdict_accuracy: float = 0.9


@dataclass
class ReleaseGateResult:
    """Result of benchmark release-gate evaluation."""

    passed: bool
    failed_checks: list[str]
    thresholds: ReleaseGateThresholds


def _safe_div(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _finding_key(finding: LabeledFinding) -> str:
    return f"{finding.signature}|{finding.severity.value}|{finding.category.value}"


def _is_severe(finding: LabeledFinding) -> bool:
    return finding.severity in {Severity.CRITICAL, Severity.HIGH}


def _infer_blocked(findings: list[LabeledFinding]) -> bool:
    return any(_is_severe(finding) for finding in findings)


def evaluate_case(case: BenchmarkCase) -> CaseMetrics:
    """Evaluate one labeled case and compute precision/recall/verdict."""
    expected = {_finding_key(finding) for finding in case.expected_findings}
    predicted = {_finding_key(finding) for finding in case.predicted_findings}

    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    expected_severe = {_finding_key(finding) for finding in case.expected_findings if _is_severe(finding)}
    predicted_severe = {
        _finding_key(finding) for finding in case.predicted_findings if _is_severe(finding)
    }
    severe_tp = len(expected_severe & predicted_severe)
    severe_recall = _safe_div(severe_tp, len(expected_severe))

    expected_blocked = case.expected_blocked
    if expected_blocked is None:
        expected_blocked = _infer_blocked(case.expected_findings)

    predicted_blocked = case.predicted_blocked
    if predicted_blocked is None:
        predicted_blocked = _infer_blocked(case.predicted_findings)

    return CaseMetrics(
        case_id=case.case_id,
        language=case.language,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        severe_recall=round(severe_recall, 4),
        verdict_correct=expected_blocked == predicted_blocked,
    )


def evaluate_benchmark(dataset: BenchmarkDataset) -> BenchmarkMetrics:
    """Evaluate all cases in dataset."""
    if not dataset.cases:
        return BenchmarkMetrics(
            case_metrics=[],
            total_cases=0,
            mean_precision=0.0,
            mean_recall=0.0,
            mean_f1=0.0,
            mean_severe_recall=0.0,
            verdict_accuracy=0.0,
        )

    case_metrics = [evaluate_case(case) for case in dataset.cases]
    total = len(case_metrics)

    return BenchmarkMetrics(
        case_metrics=case_metrics,
        total_cases=total,
        mean_precision=round(sum(metric.precision for metric in case_metrics) / total, 4),
        mean_recall=round(sum(metric.recall for metric in case_metrics) / total, 4),
        mean_f1=round(sum(metric.f1 for metric in case_metrics) / total, 4),
        mean_severe_recall=round(sum(metric.severe_recall for metric in case_metrics) / total, 4),
        verdict_accuracy=round(
            _safe_div(sum(1 for metric in case_metrics if metric.verdict_correct), total), 4
        ),
    )


def evaluate_release_gate(
    report: BenchmarkMetrics,
    thresholds: ReleaseGateThresholds | None = None,
) -> ReleaseGateResult:
    """Evaluate benchmark report against release thresholds."""
    gate = thresholds or ReleaseGateThresholds()
    failures: list[str] = []
    if report.mean_precision < gate.min_mean_precision:
        failures.append(
            f"mean_precision {report.mean_precision:.4f} < {gate.min_mean_precision:.4f}"
        )
    if report.mean_recall < gate.min_mean_recall:
        failures.append(f"mean_recall {report.mean_recall:.4f} < {gate.min_mean_recall:.4f}")
    if report.mean_f1 < gate.min_mean_f1:
        failures.append(f"mean_f1 {report.mean_f1:.4f} < {gate.min_mean_f1:.4f}")
    if report.mean_severe_recall < gate.min_severe_recall:
        failures.append(
            f"mean_severe_recall {report.mean_severe_recall:.4f} < {gate.min_severe_recall:.4f}"
        )
    if report.verdict_accuracy < gate.min_verdict_accuracy:
        failures.append(
            f"verdict_accuracy {report.verdict_accuracy:.4f} < {gate.min_verdict_accuracy:.4f}"
        )

    return ReleaseGateResult(
        passed=len(failures) == 0,
        failed_checks=failures,
        thresholds=gate,
    )


def _build_scorecard(group: str, metrics: list[CaseMetrics]) -> Scorecard:
    """Build scorecard for grouped metrics."""
    total = len(metrics)
    return Scorecard(
        group=group,
        cases=total,
        mean_precision=round(fmean(m.precision for m in metrics), 4),
        mean_recall=round(fmean(m.recall for m in metrics), 4),
        mean_f1=round(fmean(m.f1 for m in metrics), 4),
        severe_recall=round(fmean(m.severe_recall for m in metrics), 4),
        verdict_accuracy=round(_safe_div(sum(1 for m in metrics if m.verdict_correct), total), 4),
    )


def scorecards_by_language(dataset: BenchmarkDataset) -> list[Scorecard]:
    """Compute scorecards grouped by language."""
    grouped: dict[str, list[CaseMetrics]] = defaultdict(list)
    for case in dataset.cases:
        grouped[case.language].append(evaluate_case(case))
    return [_build_scorecard(language, metrics) for language, metrics in sorted(grouped.items())]


def scorecards_by_repo_family(dataset: BenchmarkDataset) -> list[Scorecard]:
    """Compute scorecards grouped by repository family."""
    grouped: dict[str, list[CaseMetrics]] = defaultdict(list)
    for case in dataset.cases:
        grouped[case.repo_family].append(evaluate_case(case))
    return [_build_scorecard(family, metrics) for family, metrics in sorted(grouped.items())]


def validate_dataset_coverage(
    dataset: BenchmarkDataset,
    min_total_cases: int = 50,
    required_languages: list[str] | None = None,
    min_cases_per_language: int = 5,
) -> DatasetValidation:
    """Validate labeled corpus readiness for reliable benchmarking."""
    required = required_languages or ["python", "javascript", "typescript", "java", "go", "rust", "cpp"]
    language_counts: dict[str, int] = defaultdict(int)
    for case in dataset.cases:
        language_counts[case.language.lower()] += 1

    issues: list[str] = []
    total_cases = len(dataset.cases)
    if total_cases < min_total_cases:
        issues.append(f"Dataset has {total_cases} cases; requires at least {min_total_cases}.")

    for language in required:
        count = language_counts.get(language.lower(), 0)
        if count < min_cases_per_language:
            issues.append(
                f"Language '{language}' has {count} cases; requires at least {min_cases_per_language}."
            )

    return DatasetValidation(
        valid=len(issues) == 0,
        issues=issues,
        total_cases=total_cases,
        language_counts=dict(language_counts),
    )


def benchmark_report_markdown(
    aggregate: BenchmarkMetrics,
    language_cards: list[Scorecard],
    repo_family_cards: list[Scorecard],
) -> str:
    """Render benchmark report as markdown."""
    lines = [
        "# Professor Benchmark Report",
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Cases | {aggregate.total_cases} |",
        f"| Mean Precision | {aggregate.mean_precision:.4f} |",
        f"| Mean Recall | {aggregate.mean_recall:.4f} |",
        f"| Mean F1 | {aggregate.mean_f1:.4f} |",
        f"| Severe Recall | {aggregate.mean_severe_recall:.4f} |",
        f"| Verdict Accuracy | {aggregate.verdict_accuracy:.4f} |",
        "",
        "## By Language",
        "",
        "| Language | Cases | Precision | Recall | F1 | Severe Recall | Verdict Accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for card in language_cards:
        lines.append(
            f"| {card.group} | {card.cases} | {card.mean_precision:.4f} | {card.mean_recall:.4f} | "
            f"{card.mean_f1:.4f} | {card.severe_recall:.4f} | {card.verdict_accuracy:.4f} |"
        )

    lines.extend(
        [
            "",
            "## By Repo Family",
            "",
            "| Repo Family | Cases | Precision | Recall | F1 | Severe Recall | Verdict Accuracy |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for card in repo_family_cards:
        lines.append(
            f"| {card.group} | {card.cases} | {card.mean_precision:.4f} | {card.mean_recall:.4f} | "
            f"{card.mean_f1:.4f} | {card.severe_recall:.4f} | {card.verdict_accuracy:.4f} |"
        )

    return "\n".join(lines) + "\n"


def benchmark_report_json(
    aggregate: BenchmarkMetrics,
    language_cards: list[Scorecard],
    repo_family_cards: list[Scorecard],
) -> str:
    """Render benchmark report as JSON string."""
    payload = {
        "aggregate": {
            "total_cases": aggregate.total_cases,
            "mean_precision": aggregate.mean_precision,
            "mean_recall": aggregate.mean_recall,
            "mean_f1": aggregate.mean_f1,
            "mean_severe_recall": aggregate.mean_severe_recall,
            "verdict_accuracy": aggregate.verdict_accuracy,
        },
        "language_scorecards": [
            {
                "group": card.group,
                "cases": card.cases,
                "mean_precision": card.mean_precision,
                "mean_recall": card.mean_recall,
                "mean_f1": card.mean_f1,
                "severe_recall": card.severe_recall,
                "verdict_accuracy": card.verdict_accuracy,
            }
            for card in language_cards
        ],
        "repo_family_scorecards": [
            {
                "group": card.group,
                "cases": card.cases,
                "mean_precision": card.mean_precision,
                "mean_recall": card.mean_recall,
                "mean_f1": card.mean_f1,
                "severe_recall": card.severe_recall,
                "verdict_accuracy": card.verdict_accuracy,
            }
            for card in repo_family_cards
        ],
    }
    return json.dumps(payload, indent=2)


def load_benchmark_dataset(path: Path) -> BenchmarkDataset:
    """Load benchmark dataset JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[BenchmarkCase] = []

    for row in raw.get("cases", []):
        expected = [LabeledFinding.from_dict(item) for item in row.get("expected_findings", [])]
        predicted = [LabeledFinding.from_dict(item) for item in row.get("predicted_findings", [])]
        cases.append(
            BenchmarkCase(
                case_id=row["case_id"],
                language=row.get("language", "unknown"),
                expected_findings=expected,
                predicted_findings=predicted,
                expected_blocked=row.get("expected_blocked"),
                predicted_blocked=row.get("predicted_blocked"),
                repo_family=row.get("repo_family", "unknown"),
                source_url=row.get("source_url", ""),
                notes=row.get("notes", ""),
            )
        )

    return BenchmarkDataset(cases=cases)


def evaluate_curation_status(
    dataset: BenchmarkDataset,
    min_expected_findings: int = 1,
    require_source_url: bool = True,
) -> CurationStatus:
    """Evaluate whether corpus cases are fully curated."""
    total = len(dataset.cases)
    if total == 0:
        return CurationStatus(
            valid=False,
            total_cases=0,
            curated_cases=0,
            completion_ratio=0.0,
            by_language={},
            pending_case_ids=[],
            issues=["Dataset has no cases."],
        )

    pending: list[str] = []
    language_totals: dict[str, int] = defaultdict(int)
    language_curated: dict[str, int] = defaultdict(int)

    for case in dataset.cases:
        language = case.language.lower()
        language_totals[language] += 1

        has_findings = len(case.expected_findings) >= min_expected_findings
        has_source = bool(case.source_url.strip()) if require_source_url else True

        if has_findings and has_source:
            language_curated[language] += 1
        else:
            pending.append(case.case_id)

    curated_cases = total - len(pending)
    by_language = {
        language: round(_safe_div(language_curated.get(language, 0), count), 4)
        for language, count in language_totals.items()
    }

    issues: list[str] = []
    if curated_cases < total:
        issues.append(f"{len(pending)} case(s) still missing curation requirements.")
    if require_source_url and any(not case.source_url.strip() for case in dataset.cases):
        issues.append("Some cases are missing source_url metadata.")
    if any(len(case.expected_findings) < min_expected_findings for case in dataset.cases):
        issues.append("Some cases are missing expected findings labels.")

    return CurationStatus(
        valid=len(issues) == 0,
        total_cases=total,
        curated_cases=curated_cases,
        completion_ratio=round(_safe_div(curated_cases, total), 4),
        by_language=by_language,
        pending_case_ids=pending,
        issues=issues,
    )


def generate_corpus_template(
    output_path: Path,
    language_targets: dict[str, int] | None = None,
) -> dict[str, object]:
    """Generate labeled corpus template JSON for benchmark curation."""
    targets = language_targets or DEFAULT_LANGUAGE_TARGETS
    repo_family_cycle = [
        "backend",
        "frontend",
        "infra",
        "systems",
        "data",
    ]

    cases: list[dict[str, object]] = []
    cursor = 0
    for language, count in targets.items():
        for index in range(1, count + 1):
            repo_family = repo_family_cycle[cursor % len(repo_family_cycle)]
            cursor += 1
            cases.append(
                {
                    "case_id": f"{language[:3]}-{index:03d}",
                    "language": language,
                    "repo_family": repo_family,
                    "source_url": "",
                    "notes": "",
                    "expected_findings": [],
                    "predicted_findings": [],
                }
            )

    payload: dict[str, object] = {
        "meta": {
            "description": "Professor benchmark corpus template",
            "total_cases": len(cases),
            "language_targets": targets,
            "curation_guide": "Fill expected_findings with validated ground truth findings.",
        },
        "cases": cases,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def update_corpus_case(
    corpus_path: Path,
    case_id: str,
    *,
    source_url: str | None = None,
    notes: str | None = None,
    expected_finding: dict[str, str] | None = None,
    predicted_finding: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Update one corpus case with metadata/findings and persist changes."""
    raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])
    target_case: dict[str, Any] | None = None

    for row in cases:
        if row.get("case_id") == case_id:
            target_case = row
            break

    if target_case is None:
        raise ValueError(f"Case '{case_id}' not found in corpus.")

    if source_url is not None:
        target_case["source_url"] = source_url
    if notes is not None:
        target_case["notes"] = notes

    if expected_finding is not None:
        _validate_finding_payload(expected_finding)
        target_case.setdefault("expected_findings", []).append(expected_finding)
    if predicted_finding is not None:
        _validate_finding_payload(predicted_finding)
        target_case.setdefault("predicted_findings", []).append(predicted_finding)

    corpus_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    return {
        "case_id": case_id,
        "expected_count": len(target_case.get("expected_findings", [])),
        "predicted_count": len(target_case.get("predicted_findings", [])),
        "source_url_set": bool(str(target_case.get("source_url", "")).strip()),
    }


def update_corpus_cases(
    corpus_path: Path,
    updates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply multiple case updates atomically and persist once."""
    raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])
    case_map = {row.get("case_id"): row for row in cases}
    results: list[dict[str, Any]] = []

    # Validate first (fail-fast) before mutating.
    for update in updates:
        case_id = str(update.get("case_id", "")).strip()
        if not case_id:
            raise ValueError("Each update item must include non-empty 'case_id'.")
        if case_id not in case_map:
            raise ValueError(f"Case '{case_id}' not found in corpus.")

        if update.get("expected_finding") is not None:
            _validate_finding_payload(update["expected_finding"])
        if update.get("predicted_finding") is not None:
            _validate_finding_payload(update["predicted_finding"])

    # Apply updates.
    for update in updates:
        case_id = update["case_id"]
        target_case = case_map[case_id]

        if "source_url" in update and update["source_url"] is not None:
            target_case["source_url"] = update["source_url"]
        if "notes" in update and update["notes"] is not None:
            target_case["notes"] = update["notes"]
        if update.get("expected_finding") is not None:
            target_case.setdefault("expected_findings", []).append(update["expected_finding"])
        if update.get("predicted_finding") is not None:
            target_case.setdefault("predicted_findings", []).append(update["predicted_finding"])

        results.append(
            {
                "case_id": case_id,
                "expected_count": len(target_case.get("expected_findings", [])),
                "predicted_count": len(target_case.get("predicted_findings", [])),
                "source_url_set": bool(str(target_case.get("source_url", "")).strip()),
            }
        )

    corpus_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return results


def load_curation_updates(path: Path) -> list[dict[str, Any]]:
    """Load curation updates list from JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    updates = raw.get("updates")
    if not isinstance(updates, list):
        raise ValueError("Updates file must contain an 'updates' array.")
    return updates


def generate_curation_work_items(
    dataset: BenchmarkDataset,
    per_language_limit: int = 3,
) -> dict[str, Any]:
    """Generate pending-case work items grouped by language."""
    pending_by_language: dict[str, list[str]] = defaultdict(list)
    for case in dataset.cases:
        has_findings = len(case.expected_findings) > 0
        has_source = bool(case.source_url.strip())
        if not (has_findings and has_source):
            pending_by_language[case.language.lower()].append(case.case_id)

    updates: list[dict[str, Any]] = []
    for language, case_ids in sorted(pending_by_language.items()):
        for case_id in case_ids[: max(0, per_language_limit)]:
            updates.append(
                {
                    "case_id": case_id,
                    "source_url": "",
                    "notes": f"triage:{language}",
                    "expected_finding": {
                        "signature": "",
                        "severity": "high",
                        "category": "bug",
                    },
                }
            )

    return {
        "meta": {
            "description": "Professor curation work items",
            "per_language_limit": per_language_limit,
            "total_updates": len(updates),
        },
        "updates": updates,
    }


def _validate_finding_payload(finding: dict[str, str]) -> None:
    required = {"signature", "severity", "category"}
    missing = [key for key in required if key not in finding or not str(finding[key]).strip()]
    if missing:
        raise ValueError(f"Finding payload missing required fields: {', '.join(sorted(missing))}")
    Severity(str(finding["severity"]).lower())
    FindingCategory(str(finding["category"]).lower())

