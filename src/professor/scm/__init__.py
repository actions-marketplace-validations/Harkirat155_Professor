"""SCM (Source Control Management) integration module."""

from professor.scm.github import (
    GitHubClient,
    PullRequest,
    FileChange,
    GitHubError,
    GitHubRateLimitError,
)

__all__ = [
    "GitHubClient",
    "PullRequest",
    "FileChange",
    "GitHubError",
    "GitHubRateLimitError",
]
