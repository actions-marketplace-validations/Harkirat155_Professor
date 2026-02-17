"""Command-line interface for Professor."""

import asyncio
import json
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from professor import __version__
from professor.config import get_settings
from professor.logging import setup_logging, get_logger
from professor.reviewer import PRReviewer
from professor.core import Severity
from professor.benchmark import (
    DEFAULT_LANGUAGE_TARGETS,
    benchmark_report_json,
    benchmark_report_markdown,
    evaluate_benchmark,
    evaluate_curation_status,
    evaluate_release_gate,
    generate_curation_work_items,
    generate_corpus_template,
    load_curation_updates,
    load_benchmark_dataset,
    scorecards_by_language,
    scorecards_by_repo_family,
    ReleaseGateThresholds,
    update_corpus_case,
    update_corpus_cases,
    validate_dataset_coverage,
)

console = Console()
logger = get_logger(__name__)


async def _run_review(
    owner: str, repo: str, pr_number: int, post_comments: bool, min_severity: str
) -> None:
    """Run PR review asynchronously."""
    settings = get_settings()

    # Initialize clients
    console.print(f"[blue]Initializing Professor for {owner}/{repo}#{pr_number}...[/blue]")

    if not settings.github.token:
        console.print("[red]Error: GITHUB_TOKEN not set in environment[/red]")
        console.print("[yellow]Set GITHUB_TOKEN in .env file or environment[/yellow]")
        return

    from professor.scm.github import GitHubClient

    github_client = GitHubClient(settings.github.token)

    # Initialize LLM client based on config
    if settings.llm.provider == "anthropic":
        from professor.llm import AnthropicClient

        if not settings.llm.anthropic_api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
            return
        llm_client = AnthropicClient(
            api_key=settings.llm.anthropic_api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    elif settings.llm.provider == "openai":
        from professor.llm import OpenAIClient

        if not settings.llm.openai_api_key:
            console.print("[red]Error: OPENAI_API_KEY not set[/red]")
            return
        llm_client = OpenAIClient(
            api_key=settings.llm.openai_api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    else:
        console.print(f"[red]Error: Unknown LLM provider: {settings.llm.provider}[/red]")
        return

    # Create reviewer
    reviewer = PRReviewer(
        github_client=github_client,
        llm_client=llm_client,
        max_files=settings.review.max_review_files,
        max_file_size_kb=settings.review.max_file_size_kb,
    )

    # Run review with progress indicator
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Reviewing PR...", total=None)

        try:
            result = await reviewer.review_pull_request(owner, repo, pr_number)
            progress.update(task, completed=True)

            # Display results
            console.print()
            console.print(Panel.fit(
                f"[bold green]✓ Review Complete![/bold green]\n"
                f"PR: {result.pr.title}\n"
                f"Author: {result.pr.author}\n"
                f"Files Analyzed: {result.review.summary.files_analyzed}\n"
                f"Cost: ${result.cost:.4f}\n"
                f"Verdict: {result.verdict.upper()}\n"
                f"Confidence: {result.confidence:.2f}",
                border_style="green"
            ))

            # Show findings summary
            console.print()
            table = Table(title="📊 Review Summary")
            table.add_column("Severity", style="cyan")
            table.add_column("Count", style="magenta", justify="right")

            table.add_row("Critical", str(result.review.summary.critical), style="red bold")
            table.add_row("High", str(result.review.summary.high), style="red")
            table.add_row("Medium", str(result.review.summary.medium), style="yellow")
            table.add_row("Low", str(result.review.summary.low), style="blue")
            table.add_row("Info", str(result.review.summary.info), style="dim")
            table.add_row("", "")
            table.add_row("Total", str(result.review.summary.total_findings), style="bold")

            console.print(table)

            # Show findings
            min_sev = Severity(min_severity)
            severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
            filtered_findings = [
                f for f in result.review.findings
                if severity_order.index(f.severity) <= severity_order.index(min_sev)
            ]

            if filtered_findings:
                console.print()
                console.print(f"[bold]🔍 Findings (>= {min_severity}):[/bold]")
                for finding in filtered_findings:
                    severity_colors = {
                        Severity.CRITICAL: "red bold",
                        Severity.HIGH: "red",
                        Severity.MEDIUM: "yellow",
                        Severity.LOW: "blue",
                        Severity.INFO: "dim",
                    }
                    color = severity_colors.get(finding.severity, "white")

                    console.print()
                    console.print(f"[{color}]● {finding.severity.upper()}[/{color}] {finding.title}")
                    console.print(f"  📍 {finding.location}")
                    console.print(f"  💬 {finding.message}")
                    if finding.suggestion:
                        console.print(f"  💡 [dim]Suggestion: {finding.suggestion}[/dim]")

            # Show approval status
            console.print()
            if result.approved:
                console.print("[bold green]✓ PR APPROVED - No blocking issues found[/bold green]")
            else:
                console.print(f"[bold red]✗ PR BLOCKED - {result.blocking_issues} blocking issue(s)[/bold red]")

        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[red]Error during review: {e}[/red]")
            logger.error("review_failed", error=str(e))
            raise


@click.group()
@click.version_option(version=__version__)
@click.option("--config", type=click.Path(exists=True), help="Configuration file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(config: Optional[str], verbose: bool) -> None:
    """🎓 Professor - AI-Powered Code Review & Quality Oversight

    Professor ensures that every line of code, whether written by human or machine,
    meets the highest standards of quality, security, and correctness.
    """
    setup_logging()
    if verbose:
        settings = get_settings()
        settings.log.level = "DEBUG"

    if config:
        console.print(f"[blue]Loading configuration from: {config}[/blue]")


@cli.command()
@click.option("--pr-url", help="Pull request URL to review (e.g., https://github.com/owner/repo/pull/123)")
@click.option("--owner", help="Repository owner")
@click.option("--repo", help="Repository name")
@click.option("--pr-number", type=int, help="Pull request number")
@click.option("--post-comments", is_flag=True, help="Post review comments to GitHub")
@click.option("--min-severity", type=click.Choice(["critical", "high", "medium", "low", "info"]), default="medium", help="Minimum severity to report")
def review(
    pr_url: Optional[str],
    owner: Optional[str],
    repo: Optional[str],
    pr_number: Optional[int],
    post_comments: bool,
    min_severity: str,
) -> None:
    """Review a pull request and generate findings.

    Examples:
        professor review --pr-url https://github.com/owner/repo/pull/123
        professor review --owner octocat --repo Hello-World --pr-number 1
    """
    console.print(Panel.fit(
        "[bold cyan]🎓 Professor Code Review[/bold cyan]\n"
        "Analyzing code with superhuman precision...",
        border_style="cyan"
    ))

    # Parse PR URL if provided
    if pr_url:
        import re
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
        if match:
            owner, repo, pr_number = match.groups()
            pr_number = int(pr_number)
        else:
            console.print("[red]Error: Invalid PR URL format[/red]")
            return

    # Validate we have all required info
    if not (owner and repo and pr_number):
        console.print("[red]Error: Specify either --pr-url or --owner, --repo, --pr-number[/red]")
        return

    # Run async review
    asyncio.run(_run_review(owner, repo, pr_number, post_comments, min_severity))


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Choice(["json", "markdown", "text"]), default="text", help="Output format")
def analyze(path: str, output: str) -> None:
    """Analyze code at the specified path."""
    console.print(f"[blue]Analyzing: {path}[/blue]")
    console.print(f"[blue]Output format: {output}[/blue]")
    
    # TODO: Implement analysis
    console.print("[yellow]Analysis not yet implemented[/yellow]")


@cli.command()
@click.option("--days", type=int, default=30, help="Number of days to report")
def stats(days: int) -> None:
    """Show review statistics and metrics."""
    console.print(f"[blue]Showing statistics for the last {days} days[/blue]")
    
    # TODO: Implement stats from database
    table = Table(title="📊 Professor Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Total Reviews", "0")
    table.add_row("Total Findings", "0")
    table.add_row("Critical Issues", "0")
    table.add_row("High Issues", "0")
    table.add_row("Files Analyzed", "0")
    
    console.print(table)
    console.print("[yellow]Statistics tracking not yet implemented[/yellow]")


@cli.command("benchmark")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.option("--output-json", "output_json_path", type=click.Path(), help="Write JSON report to file")
@click.option(
    "--output-markdown",
    "output_markdown_path",
    type=click.Path(),
    help="Write markdown report to file",
)
@click.option("--strict", is_flag=True, help="Fail benchmark if dataset coverage is insufficient")
@click.option("--enforce-gate", is_flag=True, help="Fail if release gate thresholds are not met")
@click.option("--min-precision", type=float, default=0.9, show_default=True)
@click.option("--min-recall", type=float, default=0.85, show_default=True)
@click.option("--min-f1", type=float, default=0.87, show_default=True)
@click.option("--min-severe-recall", type=float, default=0.95, show_default=True)
@click.option("--min-verdict-accuracy", type=float, default=0.9, show_default=True)
def benchmark(
    dataset_path: str,
    output_json_path: Optional[str],
    output_markdown_path: Optional[str],
    strict: bool,
    enforce_gate: bool,
    min_precision: float,
    min_recall: float,
    min_f1: float,
    min_severe_recall: float,
    min_verdict_accuracy: float,
) -> None:
    """Evaluate labeled PR benchmark dataset."""
    dataset = load_benchmark_dataset(Path(dataset_path))
    report = evaluate_benchmark(dataset)
    gate = evaluate_release_gate(
        report,
        ReleaseGateThresholds(
            min_mean_precision=min_precision,
            min_mean_recall=min_recall,
            min_mean_f1=min_f1,
            min_severe_recall=min_severe_recall,
            min_verdict_accuracy=min_verdict_accuracy,
        ),
    )
    language_cards = scorecards_by_language(dataset)
    family_cards = scorecards_by_repo_family(dataset)
    coverage = validate_dataset_coverage(dataset)

    console.print(Panel.fit("[bold cyan]🎯 Benchmark Report[/bold cyan]", border_style="cyan"))
    summary = Table(show_header=True, header_style="bold magenta")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="yellow")
    summary.add_row("Cases", str(report.total_cases))
    summary.add_row("Mean Precision", f"{report.mean_precision:.4f}")
    summary.add_row("Mean Recall", f"{report.mean_recall:.4f}")
    summary.add_row("Mean F1", f"{report.mean_f1:.4f}")
    summary.add_row("Severe Recall", f"{report.mean_severe_recall:.4f}")
    summary.add_row("Verdict Accuracy", f"{report.verdict_accuracy:.4f}")
    summary.add_row("Coverage Ready", "yes" if coverage.valid else "no")
    summary.add_row("Release Gate", "pass" if gate.passed else "fail")
    console.print(summary)

    lang_table = Table(title="🌐 Language Scorecards")
    lang_table.add_column("Language", style="cyan")
    lang_table.add_column("Cases", justify="right", style="yellow")
    lang_table.add_column("F1", justify="right", style="magenta")
    lang_table.add_column("Severe Recall", justify="right", style="magenta")
    for card in language_cards:
        lang_table.add_row(card.group, str(card.cases), f"{card.mean_f1:.4f}", f"{card.severe_recall:.4f}")
    console.print(lang_table)

    if output_markdown_path:
        markdown = benchmark_report_markdown(report, language_cards, family_cards)
        Path(output_markdown_path).write_text(markdown, encoding="utf-8")
        console.print(f"[green]✓ Wrote markdown report to {output_markdown_path}[/green]")

    if output_json_path:
        json_report = benchmark_report_json(report, language_cards, family_cards)
        Path(output_json_path).write_text(json_report, encoding="utf-8")
        console.print(f"[green]✓ Wrote JSON report to {output_json_path}[/green]")

    if not coverage.valid:
        console.print("[yellow]Dataset coverage issues detected:[/yellow]")
        for issue in coverage.issues:
            console.print(f"[yellow]- {issue}[/yellow]")
        if strict:
            raise click.ClickException("Benchmark coverage validation failed in strict mode.")
    if not gate.passed:
        console.print("[yellow]Release gate failures:[/yellow]")
        for item in gate.failed_checks:
            console.print(f"[yellow]- {item}[/yellow]")
        if enforce_gate:
            raise click.ClickException("Benchmark release gate failed.")


@cli.command("benchmark-init")
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default="examples\\benchmark_corpus_50.json",
    show_default=True,
    help="Path for generated corpus template",
)
def benchmark_init(output_path: str) -> None:
    """Generate default 50-case benchmark corpus template."""
    target = Path(output_path)
    if not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)

    payload = generate_corpus_template(target, DEFAULT_LANGUAGE_TARGETS)
    total_cases = payload.get("meta", {}).get("total_cases", 0)
    console.print(f"[green]✓ Generated corpus template: {output_path}[/green]")
    console.print(f"[blue]Total cases: {total_cases}[/blue]")


@cli.command("benchmark-curation-status")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, help="Fail if corpus is not fully curated")
@click.option("--top-pending", type=int, default=10, show_default=True, help="Show first N pending case IDs")
def benchmark_curation_status(dataset_path: str, strict: bool, top_pending: int) -> None:
    """Show corpus curation completeness and missing labels."""
    dataset = load_benchmark_dataset(Path(dataset_path))
    status = evaluate_curation_status(dataset)

    table = Table(title="🧪 Benchmark Curation Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_row("Total Cases", str(status.total_cases))
    table.add_row("Curated Cases", str(status.curated_cases))
    table.add_row("Completion", f"{status.completion_ratio:.2%}")
    table.add_row("Ready", "yes" if status.valid else "no")
    console.print(table)

    lang_table = Table(title="🌐 Curation by Language")
    lang_table.add_column("Language", style="cyan")
    lang_table.add_column("Completion", style="magenta", justify="right")
    for language, ratio in sorted(status.by_language.items()):
        lang_table.add_row(language, f"{ratio:.2%}")
    console.print(lang_table)

    if status.pending_case_ids:
        console.print("[yellow]Pending case IDs:[/yellow]")
        for case_id in status.pending_case_ids[:top_pending]:
            console.print(f"[yellow]- {case_id}[/yellow]")
        if len(status.pending_case_ids) > top_pending:
            console.print(f"[yellow]... and {len(status.pending_case_ids) - top_pending} more[/yellow]")

    for issue in status.issues:
        console.print(f"[yellow]- {issue}[/yellow]")

    if strict and not status.valid:
        raise click.ClickException("Corpus curation is incomplete.")


@cli.command("benchmark-curation-update")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.option("--case-id", required=True, help="Case ID to update")
@click.option("--source-url", help="Source PR URL or reference")
@click.option("--notes", help="Curation notes")
@click.option("--expected-signature", help="Expected finding signature")
@click.option("--expected-severity", type=click.Choice(["critical", "high", "medium", "low", "info"]))
@click.option(
    "--expected-category",
    type=click.Choice(
        ["bug", "security", "performance", "maintainability", "style", "documentation", "testing", "architecture"]
    ),
)
@click.option("--predicted-signature", help="Predicted finding signature")
@click.option("--predicted-severity", type=click.Choice(["critical", "high", "medium", "low", "info"]))
@click.option(
    "--predicted-category",
    type=click.Choice(
        ["bug", "security", "performance", "maintainability", "style", "documentation", "testing", "architecture"]
    ),
)
def benchmark_curation_update(
    dataset_path: str,
    case_id: str,
    source_url: Optional[str],
    notes: Optional[str],
    expected_signature: Optional[str],
    expected_severity: Optional[str],
    expected_category: Optional[str],
    predicted_signature: Optional[str],
    predicted_severity: Optional[str],
    predicted_category: Optional[str],
) -> None:
    """Update one corpus case with labels/metadata."""
    expected_finding = None
    predicted_finding = None

    if expected_signature or expected_severity or expected_category:
        if not (expected_signature and expected_severity and expected_category):
            raise click.ClickException(
                "Expected finding requires --expected-signature, --expected-severity, and --expected-category."
            )
        expected_finding = {
            "signature": expected_signature,
            "severity": expected_severity,
            "category": expected_category,
        }

    if predicted_signature or predicted_severity or predicted_category:
        if not (predicted_signature and predicted_severity and predicted_category):
            raise click.ClickException(
                "Predicted finding requires --predicted-signature, --predicted-severity, and --predicted-category."
            )
        predicted_finding = {
            "signature": predicted_signature,
            "severity": predicted_severity,
            "category": predicted_category,
        }

    if source_url is None and notes is None and expected_finding is None and predicted_finding is None:
        raise click.ClickException("No updates specified.")

    result = update_corpus_case(
        Path(dataset_path),
        case_id,
        source_url=source_url,
        notes=notes,
        expected_finding=expected_finding,
        predicted_finding=predicted_finding,
    )
    console.print(f"[green]✓ Updated case {result['case_id']}[/green]")
    console.print(
        f"[blue]Expected: {result['expected_count']} | Predicted: {result['predicted_count']} | "
        f"Source set: {result['source_url_set']}[/blue]"
    )


@cli.command("benchmark-curation-import")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.argument("updates_path", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, help="Fail if updates payload is invalid")
def benchmark_curation_import(dataset_path: str, updates_path: str, strict: bool) -> None:
    """Apply batch curation updates from JSON payload."""
    try:
        updates = load_curation_updates(Path(updates_path))
        results = update_corpus_cases(Path(dataset_path), updates)
    except Exception as exc:
        if strict:
            raise click.ClickException(f"Batch import failed: {exc}")
        console.print(f"[red]Batch import failed: {exc}[/red]")
        return

    console.print(f"[green]✓ Applied {len(results)} curation updates[/green]")
    table = Table(title="🧩 Batch Curation Results")
    table.add_column("Case ID", style="cyan")
    table.add_column("Expected", justify="right", style="yellow")
    table.add_column("Predicted", justify="right", style="yellow")
    table.add_column("Source", justify="right", style="magenta")
    for row in results[:20]:
        table.add_row(
            row["case_id"],
            str(row["expected_count"]),
            str(row["predicted_count"]),
            "yes" if row["source_url_set"] else "no",
        )
    console.print(table)
    if len(results) > 20:
        console.print(f"[blue]... and {len(results) - 20} more updates[/blue]")


@cli.command("benchmark-curation-plan")
@click.argument("dataset_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default="examples\\curation_work_items.json",
    show_default=True,
    help="Path for generated work-item update bundle",
)
@click.option("--per-language-limit", type=int, default=3, show_default=True)
def benchmark_curation_plan(dataset_path: str, output_path: str, per_language_limit: int) -> None:
    """Generate batch work items for pending curation cases."""
    dataset = load_benchmark_dataset(Path(dataset_path))
    payload = generate_curation_work_items(dataset, per_language_limit=per_language_limit)
    target = Path(output_path)
    if not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    console.print(f"[green]✓ Wrote curation work items to {output_path}[/green]")
    console.print(f"[blue]Planned updates: {payload['meta']['total_updates']}[/blue]")

@cli.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind host")
@click.option("--port", default=8000, show_default=True, type=int, help="Bind port")
def serve_github_app(host: str, port: int) -> None:
    """Run GitHub App webhook server."""
    from professor.github_app.server import create_app
    import uvicorn

    console.print(f"[blue]Starting Professor GitHub App server on {host}:{port}[/blue]")
    uvicorn.run(create_app(), host=host, port=port)


@cli.command()
def config_show() -> None:
    """Show current configuration."""
    settings = get_settings()
    
    console.print(Panel.fit(
        "[bold cyan]🔧 Professor Configuration[/bold cyan]",
        border_style="cyan"
    ))
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Environment", settings.env)
    table.add_row("LLM Provider", settings.llm.provider)
    table.add_row("LLM Model", settings.llm.model)
    table.add_row("API Host", settings.api.host)
    table.add_row("API Port", str(settings.api.port))
    table.add_row("Log Level", settings.log.level)
    table.add_row("Max Review Files", str(settings.review.max_review_files))
    
    console.print(table)


@cli.command()
def init() -> None:
    """Initialize Professor in the current directory."""
    console.print("[blue]Initializing Professor...[/blue]")
    
    # Create default config file
    config_content = """# Professor Configuration
professor:
  version: 1
  
  standards:
    severity_threshold: medium
    auto_approve_threshold: low
    
  analyzers:
    - llm:
        provider: anthropic
        model: claude-3-5-sonnet-20240620
    - static:
        - ruff
        - mypy
        
  rules:
    max_file_changes: 50
    max_function_complexity: 15
    require_tests: true
    require_docs: true
"""
    
    config_path = Path("professor.yaml")
    if config_path.exists():
        console.print("[yellow]professor.yaml already exists[/yellow]")
        return
    
    config_path.write_text(config_content)
    console.print("[green]✓ Created professor.yaml[/green]")
    console.print("[blue]Edit professor.yaml to customize your configuration[/blue]")


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
