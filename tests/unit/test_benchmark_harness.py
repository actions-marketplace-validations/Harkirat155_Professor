"""Tests for benchmark harness and labeled PR evaluation loop."""

import json

from professor.benchmark import (
    DEFAULT_LANGUAGE_TARGETS,
    BenchmarkCase,
    BenchmarkDataset,
    LabeledFinding,
    benchmark_report_json,
    benchmark_report_markdown,
    evaluate_benchmark,
    evaluate_case,
    evaluate_curation_status,
    evaluate_release_gate,
    generate_curation_work_items,
    generate_corpus_template,
    load_curation_updates,
    load_benchmark_dataset,
    scorecards_by_language,
    scorecards_by_repo_family,
    update_corpus_case,
    update_corpus_cases,
    validate_dataset_coverage,
    ReleaseGateThresholds,
)
from professor.core import FindingCategory, Severity


def _finding(signature: str, severity: Severity) -> LabeledFinding:
    return LabeledFinding(
        signature=signature,
        severity=severity,
        category=FindingCategory.SECURITY,
    )


def test_evaluate_case_precision_recall():
    case = BenchmarkCase(
        case_id="case-1",
        language="python",
        expected_findings=[_finding("a.py:10:sql", Severity.CRITICAL)],
        predicted_findings=[
            _finding("a.py:10:sql", Severity.CRITICAL),
            _finding("a.py:20:extra", Severity.MEDIUM),
        ],
    )

    metrics = evaluate_case(case)
    assert metrics.tp == 1
    assert metrics.fp == 1
    assert metrics.fn == 0
    assert metrics.precision == 0.5
    assert metrics.recall == 1.0
    assert metrics.verdict_correct


def test_evaluate_benchmark_aggregates_metrics():
    dataset = BenchmarkDataset(
        cases=[
            BenchmarkCase(
                case_id="c1",
                language="go",
                expected_findings=[_finding("x.go:1:panic", Severity.HIGH)],
                predicted_findings=[_finding("x.go:1:panic", Severity.HIGH)],
            ),
            BenchmarkCase(
                case_id="c2",
                language="rust",
                expected_findings=[_finding("lib.rs:9:unsafe", Severity.MEDIUM)],
                predicted_findings=[],
            ),
        ]
    )
    report = evaluate_benchmark(dataset)
    assert report.total_cases == 2
    assert report.mean_precision >= 0.0
    assert report.mean_recall >= 0.0
    assert report.verdict_accuracy >= 0.0


def test_scorecards_and_coverage_validation():
    dataset = BenchmarkDataset(
        cases=[
            BenchmarkCase(
                case_id="l1",
                language="python",
                repo_family="backend",
                expected_findings=[_finding("a.py:1:x", Severity.HIGH)],
                predicted_findings=[_finding("a.py:1:x", Severity.HIGH)],
            ),
            BenchmarkCase(
                case_id="l2",
                language="go",
                repo_family="infra",
                expected_findings=[_finding("b.go:1:y", Severity.MEDIUM)],
                predicted_findings=[],
            ),
        ]
    )
    lang_cards = scorecards_by_language(dataset)
    family_cards = scorecards_by_repo_family(dataset)
    coverage = validate_dataset_coverage(
        dataset,
        min_total_cases=2,
        required_languages=["python", "go"],
        min_cases_per_language=1,
    )

    assert len(lang_cards) == 2
    assert len(family_cards) == 2
    assert coverage.valid


def test_report_renderers_include_sections():
    dataset = BenchmarkDataset(
        cases=[
            BenchmarkCase(
                case_id="r1",
                language="typescript",
                repo_family="frontend",
                expected_findings=[_finding("a.ts:9:eval", Severity.HIGH)],
                predicted_findings=[_finding("a.ts:9:eval", Severity.HIGH)],
            )
        ]
    )
    report = evaluate_benchmark(dataset)
    lang_cards = scorecards_by_language(dataset)
    family_cards = scorecards_by_repo_family(dataset)
    md = benchmark_report_markdown(report, lang_cards, family_cards)
    js = benchmark_report_json(report, lang_cards, family_cards)

    assert "## By Language" in md
    assert '"language_scorecards"' in js


def test_load_benchmark_dataset(tmp_path):
    payload = {
        "cases": [
            {
                "case_id": "json-1",
                "language": "typescript",
                "repo_family": "frontend",
                "expected_findings": [
                    {
                        "signature": "src/app.ts:42:eval",
                        "severity": "high",
                        "category": "security",
                    }
                ],
                "predicted_findings": [],
            }
        ]
    }
    dataset_file = tmp_path / "benchmark.json"
    dataset_file.write_text(json.dumps(payload), encoding="utf-8")

    dataset = load_benchmark_dataset(dataset_file)
    assert len(dataset.cases) == 1
    assert dataset.cases[0].case_id == "json-1"
    assert dataset.cases[0].expected_findings[0].severity == Severity.HIGH
    assert dataset.cases[0].repo_family == "frontend"


def test_generate_corpus_template_default_targets(tmp_path):
    output = tmp_path / "corpus.json"
    payload = generate_corpus_template(output, DEFAULT_LANGUAGE_TARGETS)
    assert output.exists()
    assert payload["meta"]["total_cases"] == 50
    assert len(payload["cases"]) == 50
    languages = {case["language"] for case in payload["cases"]}
    assert {"python", "javascript", "typescript", "java", "go", "rust", "cpp"} <= languages


def test_evaluate_curation_status_flags_pending_cases():
    dataset = BenchmarkDataset(
        cases=[
            BenchmarkCase(
                case_id="ok-1",
                language="python",
                source_url="https://example.com/pr/1",
                expected_findings=[_finding("a.py:1:x", Severity.HIGH)],
                predicted_findings=[],
            ),
            BenchmarkCase(
                case_id="todo-1",
                language="go",
                source_url="",
                expected_findings=[],
                predicted_findings=[],
            ),
        ]
    )

    status = evaluate_curation_status(dataset)
    assert not status.valid
    assert status.curated_cases == 1
    assert "todo-1" in status.pending_case_ids


def test_update_corpus_case_appends_findings_and_metadata(tmp_path):
    corpus = tmp_path / "corpus.json"
    generate_corpus_template(corpus, {"python": 1})

    result = update_corpus_case(
        corpus,
        "pyt-001",
        source_url="https://github.com/org/repo/pull/1",
        notes="validated by reviewer",
        expected_finding={
            "signature": "a.py:10:sql",
            "severity": "critical",
            "category": "security",
        },
    )

    assert result["expected_count"] == 1
    dataset = load_benchmark_dataset(corpus)
    assert dataset.cases[0].source_url == "https://github.com/org/repo/pull/1"
    assert len(dataset.cases[0].expected_findings) == 1


def test_update_corpus_cases_batch(tmp_path):
    corpus = tmp_path / "corpus.json"
    generate_corpus_template(corpus, {"python": 2})

    updates = [
        {
            "case_id": "pyt-001",
            "source_url": "https://github.com/org/repo/pull/11",
            "expected_finding": {
                "signature": "a.py:1:issue",
                "severity": "high",
                "category": "security",
            },
        },
        {
            "case_id": "pyt-002",
            "notes": "triaged",
            "predicted_finding": {
                "signature": "a.py:2:issue",
                "severity": "medium",
                "category": "maintainability",
            },
        },
    ]
    results = update_corpus_cases(corpus, updates)
    assert len(results) == 2

    dataset = load_benchmark_dataset(corpus)
    assert dataset.cases[0].source_url
    assert len(dataset.cases[1].predicted_findings) == 1


def test_load_curation_updates(tmp_path):
    updates_file = tmp_path / "updates.json"
    updates_file.write_text(
        json.dumps(
            {
                "updates": [
                    {
                        "case_id": "pyt-001",
                        "notes": "checked",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    updates = load_curation_updates(updates_file)
    assert len(updates) == 1
    assert updates[0]["case_id"] == "pyt-001"


def test_generate_curation_work_items_respects_language_limit():
    dataset = BenchmarkDataset(
        cases=[
            BenchmarkCase(case_id="py-1", language="python", source_url="", expected_findings=[], predicted_findings=[]),
            BenchmarkCase(case_id="py-2", language="python", source_url="", expected_findings=[], predicted_findings=[]),
            BenchmarkCase(case_id="go-1", language="go", source_url="", expected_findings=[], predicted_findings=[]),
        ]
    )
    payload = generate_curation_work_items(dataset, per_language_limit=1)
    updates = payload["updates"]

    assert payload["meta"]["total_updates"] == 2
    case_ids = {item["case_id"] for item in updates}
    assert "go-1" in case_ids
    assert len([item for item in updates if item["case_id"].startswith("py-")]) == 1


def test_release_gate_pass_and_fail():
    passing_dataset = BenchmarkDataset(
        cases=[
            BenchmarkCase(
                case_id="ok",
                language="python",
                expected_findings=[_finding("a.py:1:x", Severity.HIGH)],
                predicted_findings=[_finding("a.py:1:x", Severity.HIGH)],
            )
        ]
    )
    passing_report = evaluate_benchmark(passing_dataset)
    passing = evaluate_release_gate(
        passing_report,
        ReleaseGateThresholds(
            min_mean_precision=0.9,
            min_mean_recall=0.9,
            min_mean_f1=0.9,
            min_severe_recall=0.9,
            min_verdict_accuracy=0.9,
        ),
    )
    assert passing.passed
    assert not passing.failed_checks

    failing_dataset = BenchmarkDataset(
        cases=[
            BenchmarkCase(
                case_id="bad",
                language="python",
                expected_findings=[_finding("a.py:1:x", Severity.HIGH)],
                predicted_findings=[],
            )
        ]
    )
    failing_report = evaluate_benchmark(failing_dataset)
    failing = evaluate_release_gate(
        failing_report,
        ReleaseGateThresholds(
            min_mean_precision=0.5,
            min_mean_recall=0.5,
            min_mean_f1=0.5,
            min_severe_recall=0.5,
            min_verdict_accuracy=0.9,
        ),
    )
    assert not failing.passed
    assert failing.failed_checks

