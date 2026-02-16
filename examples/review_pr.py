#!/usr/bin/env python3
"""
Example: Review a GitHub PR using Professor
"""

import asyncio
import os
from professor.scm.github import GitHubClient
from professor.llm import AnthropicClient
from professor.reviewer import PRReviewer
from professor.config import get_settings


async def main():
    """Run example PR review."""
    # Load settings
    settings = get_settings()

    # Check for required tokens
    github_token = settings.github.token or os.getenv("GITHUB_TOKEN")
    anthropic_key = settings.llm.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

    if not github_token:
        print("Error: GITHUB_TOKEN not set")
        print("Set it in .env file or environment variable")
        return

    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY not set")
        print("Set it in .env file or environment variable")
        return

    # Example PR to review
    # Replace with your own PR
    OWNER = "octocat"
    REPO = "Hello-World"
    PR_NUMBER = 1

    print(f"🎓 Professor - Example PR Review")
    print(f"═══════════════════════════════════")
    print(f"Reviewing: {OWNER}/{REPO}#{PR_NUMBER}")
    print()

    # Initialize clients
    print("Initializing GitHub client...")
    github_client = GitHubClient(github_token)

    print("Initializing LLM client (Anthropic Claude)...")
    llm_client = AnthropicClient(
        api_key=anthropic_key,
        model="claude-3-5-sonnet-20240620",
        temperature=0.1,
    )

    # Create reviewer
    print("Creating PR reviewer...")
    reviewer = PRReviewer(
        github_client=github_client,
        llm_client=llm_client,
        max_files=50,
        max_file_size_kb=500,
    )

    # Run review
    print(f"Starting review of PR #{PR_NUMBER}...")
    print()

    try:
        result = await reviewer.review_pull_request(OWNER, REPO, PR_NUMBER)

        # Display results
        print()
        print("═══════════════════════════════════")
        print("✓ Review Complete!")
        print(f"PR: {result.pr.title}")
        print(f"Author: {result.pr.author}")
        print(f"Files Analyzed: {result.review.summary.files_analyzed}")
        print(f"Cost: ${result.cost:.4f}")
        print()

        # Summary
        print("Review Summary:")
        print(f"  Critical: {result.review.summary.critical}")
        print(f"  High:     {result.review.summary.high}")
        print(f"  Medium:   {result.review.summary.medium}")
        print(f"  Low:      {result.review.summary.low}")
        print(f"  Info:     {result.review.summary.info}")
        print(f"  ─────────────────")
        print(f"  Total:    {result.review.summary.total_findings}")
        print()

        # Show critical and high findings
        critical_high = [
            f
            for f in result.review.findings
            if f.severity.value in ["critical", "high"]
        ]

        if critical_high:
            print("Blocking Issues (Critical/High):")
            for finding in critical_high:
                print(f"\n  [{finding.severity.upper()}] {finding.title}")
                print(f"  Location: {finding.location}")
                print(f"  Message: {finding.message}")
                if finding.suggestion:
                    print(f"  Suggestion: {finding.suggestion}")

        # Approval status
        print()
        if result.approved:
            print("✓ PR APPROVED - No blocking issues found")
        else:
            print(f"✗ PR BLOCKED - {result.blocking_issues} blocking issue(s)")

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
