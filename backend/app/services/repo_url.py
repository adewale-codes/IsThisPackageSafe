"""Shared GitHub-URL parsing, reused by every ecosystem client.

Each registry expresses "where's the source" differently (npm's package.json
repository field, PyPI's project_urls, a Maven POM's <scm><url>), but they
all eventually bottom out in a git/GitHub URL that needs the same cleanup
before it's useful to github_client.py's owner/repo lookup.
"""

from __future__ import annotations

import re
from typing import Optional

from app.models.schemas import RepositoryInfo


def parse_github_repository(raw_url: Optional[str]) -> RepositoryInfo:
    if not raw_url:
        return RepositoryInfo()

    cleaned = raw_url.strip()
    cleaned = re.sub(r"^git\+", "", cleaned)
    cleaned = re.sub(r"^scm:git:", "", cleaned)  # Maven <scm><url> sometimes uses this prefix
    cleaned = re.sub(r"^git://", "https://", cleaned)
    cleaned = re.sub(r"^git@github\.com:", "https://github.com/", cleaned)
    cleaned = re.sub(r"\.git$", "", cleaned)

    match = re.search(r"github\.com[/:]([^/]+)/([^/#]+)", cleaned)
    if not match:
        return RepositoryInfo(raw_url=raw_url)

    owner, repo = match.group(1), match.group(2)
    return RepositoryInfo(raw_url=raw_url, owner=owner, repo=repo)
