"""Command-line interface for Professor."""

import asyncio
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
from professor.scm.github import GitHubClient
from professor.llm import AnthropicClient, OpenAIClient
from professor.reviewer import PRReviewer
from professor.core import Severity

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

    github_client = GitHubClient(settings.github.token)

    # Initialize LLM client based on config
    if settings.llm.provider == "anthropic":
        if not settings.llm.anthropic_api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
            return
        llm_client = AnthropicClient(
            api_key=settings.llm.anthropic_api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    elif settings.llm.provider == "openai":
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
                f"Cost: ${result.cost:.4f}",
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
