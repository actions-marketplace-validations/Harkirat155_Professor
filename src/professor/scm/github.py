"""GitHub SCM adapter for Professor."""

from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog
from github import Github, Auth
from github.PullRequest import PullRequest as GithubPR
from github.Repository import Repository
from github.GithubException import GithubException, RateLimitExceededException

logger = structlog.get_logger()


@dataclass
class PullRequest:
    """Pull request data model."""

    number: int
    title: str
    description: str
    author: str
    base_branch: str
    head_branch: str
    state: str
    url: str
    diff_url: str
    created_at: datetime
    updated_at: datetime
    additions: int
    deletions: int
    changed_files: int
    commits: int


@dataclass
class FileChange:
    """Represents a changed file in a PR."""

    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str]
    previous_filename: Optional[str] = None


class GitHubClient:
    """GitHub API client for Professor."""

    def __init__(self, token: str) -> None:
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token or app token
        """
        auth = Auth.Token(token)
        self.client = Github(auth=auth)
        self.token = token

        logger.info("github_client_initialized")

    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int
    ) -> PullRequest:
        """Fetch pull request details.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            PullRequest object

        Raises:
            GitHubError: If PR fetch fails
        """
        try:
            repository = self.client.get_repo(f"{owner}/{repo}")
            pr = repository.get_pull(pr_number)

            logger.info(
                "fetched_pull_request",
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                title=pr.title,
            )

            return PullRequest(
                number=pr.number,
                title=pr.title,
                description=pr.body or "",
                author=pr.user.login,
                base_branch=pr.base.ref,
                head_branch=pr.head.ref,
                state=pr.state,
                url=pr.html_url,
                diff_url=pr.diff_url,
                created_at=pr.created_at,
                updated_at=pr.updated_at,
                additions=pr.additions,
                deletions=pr.deletions,
                changed_files=pr.changed_files,
                commits=pr.commits,
            )

        except RateLimitExceededException as e:
            logger.error("github_rate_limit_exceeded", error=str(e))
            raise GitHubRateLimitError("GitHub rate limit exceeded") from e
        except GithubException as e:
            logger.error("github_api_error", error=str(e), status=e.status)
            raise GitHubError(f"GitHub API error: {e}") from e
        except Exception as e:
            logger.error("unexpected_github_error", error=str(e))
            raise GitHubError(f"Unexpected error: {e}") from e

    async def get_file_changes(
        self, owner: str, repo: str, pr_number: int
    ) -> list[FileChange]:
        """Get all file changes in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of file changes

        Raises:
            GitHubError: If fetch fails
        """
        try:
            repository = self.client.get_repo(f"{owner}/{repo}")
            pr = repository.get_pull(pr_number)

            files = pr.get_files()
            changes = []

            for file in files:
                change = FileChange(
                    filename=file.filename,
                    status=file.status,
                    additions=file.additions,
                    deletions=file.deletions,
                    changes=file.changes,
                    patch=file.patch,
                    previous_filename=getattr(file, "previous_filename", None),
                )
                changes.append(change)

            logger.info(
                "fetched_file_changes",
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                file_count=len(changes),
            )

            return changes

        except GithubException as e:
            logger.error("github_api_error", error=str(e))
            raise GitHubError(f"Failed to fetch file changes: {e}") from e

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str:
        """Get file content at specific ref.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            ref: Git ref (branch, commit SHA)

        Returns:
            File content as string

        Raises:
            GitHubError: If fetch fails
        """
        try:
            repository = self.client.get_repo(f"{owner}/{repo}")
            content = repository.get_contents(path, ref=ref)

            if isinstance(content, list):
                raise GitHubError(f"Path {path} is a directory, not a file")

            return content.decoded_content.decode("utf-8")

        except GithubException as e:
            logger.error("github_api_error", error=str(e))
            raise GitHubError(f"Failed to fetch file content: {e}") from e

    async def post_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        commit_sha: str,
        path: str,
        line: int,
    ) -> None:
        """Post a review comment on a specific line.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment text
            commit_sha: Commit SHA
            path: File path
            line: Line number

        Raises:
            GitHubError: If posting fails
        """
        try:
            repository = self.client.get_repo(f"{owner}/{repo}")
            pr = repository.get_pull(pr_number)

            pr.create_review_comment(
                body=body, commit=pr.get_commits()[0], path=path, line=line
            )

            logger.info(
                "posted_review_comment",
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                path=path,
                line=line,
            )

        except GithubException as e:
            logger.error("github_api_error", error=str(e))
            raise GitHubError(f"Failed to post comment: {e}") from e

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        event: str,
        body: str,
        comments: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Create a pull request review.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            event: Review event (APPROVE, REQUEST_CHANGES, COMMENT)
            body: Review summary
            comments: List of inline comments

        Raises:
            GitHubError: If review creation fails
        """
        try:
            repository = self.client.get_repo(f"{owner}/{repo}")
            pr = repository.get_pull(pr_number)

            commit = pr.get_commits()[pr.commits - 1]

            pr.create_review(
                commit=commit, body=body, event=event, comments=comments or []
            )

            logger.info(
                "created_review",
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                event=event,
                comment_count=len(comments) if comments else 0,
            )

        except GithubException as e:
            logger.error("github_api_error", error=str(e))
            raise GitHubError(f"Failed to create review: {e}") from e

    def get_rate_limit(self) -> dict[str, Any]:
        """Get current rate limit status.

        Returns:
            Dictionary with rate limit info
        """
        rate_limit = self.client.get_rate_limit()
        return {
            "core": {
                "limit": rate_limit.core.limit,
                "remaining": rate_limit.core.remaining,
                "reset": rate_limit.core.reset,
            },
            "search": {
                "limit": rate_limit.search.limit,
                "remaining": rate_limit.search.remaining,
                "reset": rate_limit.search.reset,
            },
        }


class GitHubError(Exception):
    """Base exception for GitHub errors."""

    pass


class GitHubRateLimitError(GitHubError):
    """Raised when GitHub rate limit is exceeded."""

    pass


class GitHubAuthError(GitHubError):
    """Raised when authentication fails."""

    pass
