"""Shared test fixtures and utilities."""

import os
import re
from pathlib import Path
from typing import Any

import pytest

# Disable Rich color output for consistent test output across environments
os.environ["NO_COLOR"] = "1"

# Pattern to match ANSI escape sequences
_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(autouse=True)
def isolate_host_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep credentials, browser profiles, and archives inside each test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    for name in ("TWITTER_AUTH_TOKEN", "TWITTER_CT0", "TWITTER_TWID"):
        monkeypatch.delenv(name, raising=False)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for consistent test assertions."""
    return _ANSI_PATTERN.sub("", text)


def _make_tweet(
    tweet_id: str = "123",
    text: str = "Hello world",
    author_id: str = "456",
    author_username: str = "testuser",
    author_display_name: str = "Test User",
    created_at: str = "2025-01-01T12:00:00Z",
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a test tweet with sensible defaults.

    Args:
        tweet_id: The tweet's unique identifier.
        text: The tweet content.
        author_id: The author's unique identifier.
        author_username: The author's username.
        author_display_name: The author's display name.
        created_at: ISO 8601 timestamp of tweet creation.
        **kwargs: Additional tweet fields to include.

    Returns:
        A dictionary representing a tweet with the specified fields.
    """
    tweet = {
        "id": tweet_id,
        "text": text,
        "author_id": author_id,
        "author_username": author_username,
        "author_display_name": author_display_name,
        "created_at": created_at,
    }
    tweet.update(kwargs)
    return tweet


@pytest.fixture
def make_tweet() -> Any:
    """Fixture that provides the make_tweet factory function."""
    return _make_tweet
