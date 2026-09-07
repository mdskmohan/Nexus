"""GitHub connector.

Answers the question every incident asks second: "did we change something?"
Given a failing model, the diagnosis engine needs the commits touching that
model's lineage inside the failure window. A recent deploy is either the cause or
it is ruled out, and ruling it out is as valuable as finding it.

Also opens the pull requests that carry remediations, which is the level-2 action
in ADR-003. That write path lives behind the policy engine; this module only
reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from nexus.connectors.spec import (
    Category,
    ConnectionField,
    ConnectionTestResult,
    ConnectorSpec,
    FieldType,
)
from nexus.errors import NexusError

SYSTEM = "github"

SPEC = ConnectorSpec(
    id=SYSTEM,
    name="GitHub",
    category=Category.VERSION_CONTROL,
    description="Correlate failures with recent deployments; open remediation PRs.",
    docs_url="https://docs.github.com/en/rest",
    verified=True,
    fields=(
        ConnectionField(
            name="repository",
            label="Repository",
            placeholder="acme/analytics",
            help="In owner/name form.",
        ),
        ConnectionField(
            name="token",
            label="Access token",
            type=FieldType.SECRET,
            help="A fine-grained token with Contents: read. Add Pull requests: write "
            "only when you want Nexus to open remediation PRs.",
        ),
        ConnectionField(
            name="api_url",
            label="API URL",
            default="https://api.github.com",
            required=False,
            help="Change only for GitHub Enterprise Server.",
        ),
        ConnectionField(
            name="branch",
            label="Default branch",
            default="main",
            required=False,
            help="The branch deployments are cut from.",
        ),
    ),
)


class GitHubError(NexusError):
    """GitHub was unreachable, refused the request, or returned nonsense."""


@dataclass(frozen=True, slots=True)
class Commit:
    """One commit, reduced to what a diagnosis needs to cite it."""

    sha: str
    message: str
    author: str
    committed_at: datetime
    url: str

    @property
    def short_sha(self) -> str:
        return self.sha[:7]

    def describe(self) -> str:
        subject = self.message.strip().splitlines()[0] if self.message.strip() else ""
        return f"{self.short_sha} {subject}"


class GitHubClient:
    """Read-only client for one repository."""

    def __init__(
        self,
        repository: str,
        token: str,
        api_url: str = "https://api.github.com",
        timeout: float = 15.0,
    ) -> None:
        if "/" not in repository:
            raise GitHubError(
                f"repository must be in owner/name form, got {repository!r}"
            )
        self.repository = repository
        # The repository is NOT part of base_url: httpx normalises a base_url to
        # end in "/", which would make the repository endpoint itself resolve to
        # /repos/owner/name/ — and GitHub returns 404 for that trailing slash.
        self._prefix = f"repos/{repository}"
        self._client = httpx.Client(
            base_url=f"{api_url.rstrip('/')}/",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str = "", **params: Any) -> Any:
        """GET a path relative to this repository, e.g. "/commits" or "" for the repo."""
        url = f"{self._prefix}{path}"
        try:
            response = self._client.get(url, params=params or None)
        except httpx.HTTPError as exc:
            raise GitHubError(f"could not reach GitHub: {exc}") from exc

        if response.status_code == 401:
            raise GitHubError("GitHub rejected the token (401). It may be expired.")
        if response.status_code == 403:
            # Rate limiting and permission denial share a status; the headers
            # distinguish them, and the difference changes what the user should do.
            if response.headers.get("X-RateLimit-Remaining") == "0":
                raise GitHubError("GitHub rate limit exceeded; retry shortly.")
            raise GitHubError(
                "GitHub denied access (403). The token likely lacks Contents: read "
                f"on {self.repository}."
            )
        if response.status_code == 404:
            raise GitHubError(
                f"GitHub has no repository {self.repository}, or the token cannot see it."
            )
        if response.status_code >= 400:
            raise GitHubError(f"GitHub returned {response.status_code} for {url}")
        return response.json()

    def repository_info(self) -> dict[str, Any]:
        payload = self._get("")
        return payload if isinstance(payload, dict) else {}

    def commits(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        path: str | None = None,
        branch: str | None = None,
        limit: int = 50,
    ) -> list[Commit]:
        """Commits in a window, optionally restricted to a path.

        The path filter is what makes this useful for diagnosis: asking whether
        *anything* changed is noise, asking whether the failing model's own file
        changed is evidence.
        """
        params: dict[str, Any] = {"per_page": min(limit, 100)}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if path:
            params["path"] = path
        if branch:
            params["sha"] = branch

        payload = self._get("/commits", **params)
        if not isinstance(payload, list):
            return []

        commits: list[Commit] = []
        for item in payload:
            detail = item.get("commit") or {}
            author = (detail.get("author") or {}).get("name") or "unknown"
            raw_date = (detail.get("author") or {}).get("date")
            try:
                committed_at = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            commits.append(
                Commit(
                    sha=str(item.get("sha", "")),
                    message=str(detail.get("message", "")),
                    author=str(author),
                    committed_at=committed_at,
                    url=str(item.get("html_url", "")),
                )
            )
        return commits

    def pull_requests(self, state: str = "open", limit: int = 30) -> list[dict[str, Any]]:
        payload = self._get("/pulls", state=state, per_page=min(limit, 100))
        return payload if isinstance(payload, list) else []


def test_connection(config: dict[str, Any]) -> ConnectionTestResult:
    """Probe a GitHub configuration by reading the repository and its commits.

    Reads an actual commit rather than just repository metadata, because a token
    can often see that a repository exists while lacking Contents: read.
    """
    try:
        client = GitHubClient(
            repository=config["repository"],
            token=config["token"],
            api_url=config.get("api_url") or "https://api.github.com",
        )
    except GitHubError as exc:
        return ConnectionTestResult.failure(str(exc))
    except KeyError as exc:
        return ConnectionTestResult.failure(f"missing configuration: {exc}")

    try:
        info = client.repository_info()
        commits = client.commits(branch=config.get("branch") or None, limit=1)
    except GitHubError as exc:
        return ConnectionTestResult.failure(str(exc))
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(str(exc)[:300])
    finally:
        client.close()

    if not commits:
        return ConnectionTestResult.failure(
            f"Connected to {config['repository']}, but no commits were readable on "
            f"branch '{config.get('branch') or 'the default'}'. Check the branch name "
            "and that the token has Contents: read."
        )
    return ConnectionTestResult.success(
        f"Connected to {info.get('full_name', config['repository'])}",
        default_branch=str(info.get("default_branch", "")),
        private=str(bool(info.get("private"))).lower(),
        latest_commit=commits[0].short_sha,
    )
