"""Fetches repository signals from the GitHub REST API."""

from __future__ import annotations

import os
import re
from typing import Optional

import httpx

from app.models.schemas import GithubSignals

API_BASE = "https://api.github.com"


def _auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _contributor_count_from_link_header(link_header: Optional[str]) -> Optional[int]:
    """GitHub returns a Link header with rel="last" whose page number approximates
    the total contributor count when paginating with per_page=1."""
    if not link_header:
        return None
    match = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link_header)
    if match:
        return int(match.group(1))
    return None


async def fetch_github_signals(
    client: httpx.AsyncClient, owner: Optional[str], repo: Optional[str]
) -> GithubSignals:
    if not owner or not repo:
        return GithubSignals(linked=False)

    headers = _auth_headers()

    try:
        repo_resp = await client.get(f"{API_BASE}/repos/{owner}/{repo}", headers=headers)
    except httpx.HTTPError as exc:
        return GithubSignals(linked=True, owner=owner, repo=repo, exists=None, error=str(exc))

    if repo_resp.status_code == 404:
        return GithubSignals(linked=True, owner=owner, repo=repo, exists=False)

    if repo_resp.status_code == 403:
        return GithubSignals(
            linked=True, owner=owner, repo=repo, exists=None, error="GitHub API rate limit exceeded"
        )

    if repo_resp.status_code != 200:
        return GithubSignals(
            linked=True,
            owner=owner,
            repo=repo,
            exists=None,
            error=f"GitHub API returned status {repo_resp.status_code}",
        )

    data = repo_resp.json()

    contributors_count: Optional[int] = None
    try:
        contrib_resp = await client.get(
            f"{API_BASE}/repos/{owner}/{repo}/contributors",
            params={"per_page": 1, "anon": "true"},
            headers=headers,
        )
        if contrib_resp.status_code == 200:
            contributors_count = _contributor_count_from_link_header(
                contrib_resp.headers.get("Link")
            )
            if contributors_count is None:
                contributors_count = len(contrib_resp.json())
    except httpx.HTTPError:
        pass

    return GithubSignals(
        linked=True,
        owner=owner,
        repo=repo,
        exists=True,
        archived=data.get("archived", False),
        stars=data.get("stargazers_count"),
        forks=data.get("forks_count"),
        open_issues=data.get("open_issues_count"),
        contributors_count=contributors_count,
        last_pushed_at=data.get("pushed_at"),
    )
