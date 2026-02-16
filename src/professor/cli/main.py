"""Command-line interface for Professor."""

import asyncio
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from professor import __version__
from professor.config import get_settings
from professor.logging import setup_logging, get_logger

console = Console()
logger = get_logger(__name__)


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
@click.option("--pr-url", help="Pull request URL to review")
@click.option("--local", is_flag=True, help="Review local git changes")
@click.option("--severity", type=click.Choice(["critical", "high", "medium", "low", "info"]), default="medium", help="Minimum severity to report")
def review(pr_url: Optional[str], local: bool, severity: str) -> None:
    """Review code changes and generate findings."""
    console.print(Panel.fit(
        "[bold cyan]🎓 Professor Code Review[/bold cyan]\n"
        "Analyzing code with superhuman precision...",
        border_style="cyan"
    ))

    if pr_url:
        console.print(f"[blue]Reviewing PR: {pr_url}[/blue]")
        # TODO: Implement PR review
        console.print("[yellow]PR review not yet implemented[/yellow]")
    elif local:
        console.print("[blue]Reviewing local changes...[/blue]")
        # TODO: Implement local review
        console.print("[yellow]Local review not yet implemented[/yellow]")
    else:
        console.print("[red]Error: Specify --pr-url or --local[/red]")
        return

    console.print("[green]✓ Review complete![/green]")


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
