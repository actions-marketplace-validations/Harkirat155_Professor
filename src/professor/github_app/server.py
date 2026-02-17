"""FastAPI server for GitHub App webhook handling."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from professor.config import get_settings
from professor.logging import get_logger, setup_logging
from professor.reviewer import PRReviewer

logger = get_logger(__name__)


def verify_github_signature(body: bytes, signature_header: str | None, secret: str | None) -> bool:
    """Verify GitHub webhook signature (sha256)."""
    if not secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _build_reviewer() -> PRReviewer:
    """Create reviewer instance from runtime settings."""
    settings = get_settings()
    if not settings.github.token:
        raise ValueError("GITHUB_TOKEN is required for GitHub App review execution.")

    from professor.scm.github import GitHubClient

    if settings.llm.provider == "anthropic":
        from professor.llm import AnthropicClient

        if not settings.llm.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for anthropic provider.")
        llm_client = AnthropicClient(
            api_key=settings.llm.anthropic_api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    elif settings.llm.provider == "openai":
        from professor.llm import OpenAIClient

        if not settings.llm.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for openai provider.")
        llm_client = OpenAIClient(
            api_key=settings.llm.openai_api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm.provider}")

    return PRReviewer(
        github_client=GitHubClient(settings.github.token),
        llm_client=llm_client,
        max_files=settings.review.max_review_files,
        max_file_size_kb=settings.review.max_file_size_kb,
    )


async def _handle_pull_request_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle pull_request events and run review on active PR changes."""
    action = payload.get("action", "")
    if action not in {"opened", "reopened", "synchronize", "ready_for_review"}:
        return {"status": "ignored", "reason": f"action={action}"}

    repo_info = payload.get("repository", {})
    owner = repo_info.get("owner", {}).get("login")
    repo = repo_info.get("name")
    pr_number = payload.get("pull_request", {}).get("number")
    if not owner or not repo or not pr_number:
        raise HTTPException(status_code=400, detail="Invalid pull_request payload.")

    reviewer = _build_reviewer()
    result = await reviewer.review_pull_request(owner, repo, int(pr_number))
    logger.info(
        "github_app_review_complete",
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        verdict=result.verdict,
        confidence=result.confidence,
    )
    return {
        "status": "reviewed",
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "verdict": result.verdict,
        "confidence": result.confidence,
        "findings": result.total_findings,
    }


def create_app() -> FastAPI:
    """Create configured FastAPI app for GitHub webhooks."""
    setup_logging()
    app = FastAPI(title="Professor GitHub App", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/github")
    async def github_webhook(request: Request) -> dict[str, Any]:
        settings = get_settings()
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        event = request.headers.get("X-GitHub-Event", "")

        if not verify_github_signature(body, signature, settings.github.webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature.")

        payload = await request.json()
        if event == "ping":
            return {"status": "pong"}
        if event == "pull_request":
            return await _handle_pull_request_event(payload)
        return {"status": "ignored", "event": event}

    return app

