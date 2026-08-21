"""PyPI ecosystem client.

PyPI's JSON API (https://pypi.org/pypi/{package}/json) is, like npm's, a
single JSON document per package - no auth, current release + full release
history in one call. Two real differences from npm worth calling out:

- No install-scripts concept in the npm sense. A PyPI sdist's setup.py CAN
  run arbitrary code on install (arguably worse than npm's declared
  lifecycle scripts), but detecting "does this package have a custom
  setup.py" requires downloading and inspecting the sdist itself - out of
  scope for this phase's metadata-only client. That heuristic is left N/A
  for PyPI rather than forcing a false "clean" signal; a real follow-up
  would reuse Phase 4's tarball-fetch machinery.
- No per-version maintainer history. The JSON API only exposes the
  *current* author/maintainer, not who controlled past releases, so the
  maintainer-takeover heuristic (which needs that history) is npm-only for
  data-availability reasons, not just as a design choice.

Download stats are "best effort" via pypistats.org, a free companion
service - not part of PyPI itself. It has no documented rate limit
guarantee and returned a 429 during development, which is exactly the
"registry doesn't reliably expose this" case DownloadStats.available exists
for: fail soft, don't fake a number.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import httpx

from app.models.schemas import DownloadStats, PackageMetadata
from app.services.ecosystems.base import EcosystemClient, PackageNotFoundError
from app.services.repo_url import parse_github_repository

PYPI_BASE = "https://pypi.org/pypi"
PYPISTATS_BASE = "https://pypistats.org/api/packages"

_REPO_URL_KEY_PATTERN = re.compile(r"source|repository|code|github|homepage", re.IGNORECASE)


def _parse_upload_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _earliest_upload(files: list[dict[str, Any]]) -> Optional[datetime]:
    times = [
        t
        for f in files
        if (t := _parse_upload_time(f.get("upload_time_iso_8601") or f.get("upload_time")))
    ]
    return min(times) if times else None


def _resolve_repo_source_url(info: dict[str, Any]) -> Optional[str]:
    project_urls: dict[str, str] = info.get("project_urls") or {}

    # Prefer a project_urls entry whose *label* suggests source/repository,
    # since PyPI project owners choose their own labels (e.g. "Source Code",
    # "GitHub", "Repository") - there's no fixed key name to rely on.
    for label, url in project_urls.items():
        if url and _REPO_URL_KEY_PATTERN.search(label):
            return url

    # Fall back to any project_urls value that's obviously a GitHub link,
    # then to the deprecated top-level home_page field.
    for url in project_urls.values():
        if url and "github.com" in url:
            return url

    return info.get("home_page") or None


def _dependency_count(requires_dist: list[str]) -> int:
    # requires_dist entries with an "extra == ..." marker are optional
    # (installed only via pip install pkg[extra]); count only the
    # always-installed core dependencies for an attack-surface heuristic.
    return sum(1 for req in requires_dist if "extra ==" not in req)


def _short_license(license_value: Any) -> Optional[str]:
    if not isinstance(license_value, str) or not license_value.strip():
        return None
    value = license_value.strip()
    # A handful of PyPI packages put the entire license *text* in this
    # field instead of an identifier - truncate rather than ship a wall of
    # text as a "license name".
    return value if len(value) <= 100 else value[:97] + "..."


class PyPIClient(EcosystemClient):
    async def _fetch_json(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> dict[str, Any]:
        resp = await client.get(f"{PYPI_BASE}/{package_identifier}/json")
        if resp.status_code == 404:
            raise PackageNotFoundError("pypi", package_identifier)
        resp.raise_for_status()
        return resp.json()

    async def fetch_metadata(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> PackageMetadata:
        data = await self._fetch_json(client, package_identifier)
        info: dict[str, Any] = data.get("info") or {}
        releases: dict[str, list[dict[str, Any]]] = data.get("releases") or {}
        latest_version = info.get("version") or ""

        all_publish_times = [
            (version, t)
            for version, files in releases.items()
            if (t := _earliest_upload(files)) is not None
        ]
        first_published_at = min((t for _, t in all_publish_times), default=None)
        latest_files = releases.get(latest_version) or data.get("urls") or []
        latest_published_at = _earliest_upload(latest_files) or (
            max((t for _, t in all_publish_times), default=None)
        )

        requires_dist = [r for r in (info.get("requires_dist") or []) if isinstance(r, str)]

        return PackageMetadata(
            ecosystem="pypi",
            name=info.get("name") or package_identifier,
            description=info.get("summary") or None,
            latest_version=latest_version,
            version_count=len(releases),
            first_published_at=first_published_at,
            latest_published_at=latest_published_at,
            license=_short_license(info.get("license")),
            homepage=info.get("home_page") or (info.get("project_urls") or {}).get("Homepage"),
            keywords=(info.get("keywords") or "").split(",") if info.get("keywords") else [],
            repository=parse_github_repository(_resolve_repo_source_url(info)),
            maintainers=[],  # not exposed historically by the API - see module docstring
            dependencies={},  # PyPI deps are version-range strings, not name:version pairs
            dependency_count=_dependency_count(requires_dist),
            install_scripts={},  # N/A for PyPI - see module docstring
            tarball_url=None,  # deliberately not wired to Phase 4 deep-scan this phase
            tarball_shasum=None,
            unpacked_size_bytes=None,
        )

    async def fetch_versions(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> list[str]:
        data = await self._fetch_json(client, package_identifier)
        return sorted((data.get("releases") or {}).keys())

    async def fetch_downloads(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> DownloadStats:
        period = "last-month"
        try:
            resp = await client.get(f"{PYPISTATS_BASE}/{package_identifier}/recent")
            if resp.status_code != 200:
                return DownloadStats(period=period, downloads=0, available=False)
            data = resp.json().get("data") or {}
            last_month = data.get("last_month")
            if last_month is None:
                return DownloadStats(period=period, downloads=0, available=False)
            return DownloadStats(period=period, downloads=last_month, available=True)
        except httpx.HTTPError:
            return DownloadStats(period=period, downloads=0, available=False)
