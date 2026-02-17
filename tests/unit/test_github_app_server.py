"""Tests for GitHub App webhook server helpers."""

import hashlib
import hmac

from professor.github_app.server import verify_github_signature


def test_verify_github_signature_valid():
    body = b'{"action":"opened"}'
    secret = "super-secret"
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_github_signature(body, signature, secret)


def test_verify_github_signature_invalid():
    body = b'{"action":"opened"}'
    secret = "super-secret"
    assert not verify_github_signature(body, "sha256=deadbeef", secret)
    assert not verify_github_signature(body, None, secret)
    assert not verify_github_signature(body, "sha1=abc", secret)
    assert not verify_github_signature(body, "sha256=abc", None)

