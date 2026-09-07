"""GitHub connector."""

from nexus.connectors.github.connector import (
    SPEC,
    Commit,
    GitHubClient,
    GitHubError,
    test_connection,
)

__all__ = ["SPEC", "Commit", "GitHubClient", "GitHubError", "test_connection"]
