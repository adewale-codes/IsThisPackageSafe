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
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.models.schemas import DownloadStats, PackageMetadata, VersionEntry
from app.services.ecosystems.base import EcosystemClient, PackageNotFoundError
from app.services.repo_url import parse_github_repository

PYPI_BASE = "https://pypi.org/pypi"
PYPISTATS_BASE = "https://pypistats.org/api/packages"

_REPO_URL_KEY_PATTERN = re.compile(r"source|repository|code|github|homepage", re.IGNORECASE)

# A PEP 508 dependency spec starts with a bare distribution name (letters,
# digits, ., _, -) before any version specifier/environment marker - e.g.
# "requests (>=2.0.0)", "certifi>=2017.4.17", "numpy>=1.20; python_version>='3.8'".
_DEP_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


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


def _core_requires(requires_dist: list[str]) -> list[str]:
    # requires_dist entries with an "extra == ..." marker are optional
    # (installed only via pip install pkg[extra]); only the always-installed
    # core dependencies count for attack-surface heuristics and the Phase 8
    # dependency tree.
    return [req for req in requires_dist if "extra ==" not in req]


def _parse_dependencies(requires_dist: list[str]) -> dict[str, str]:
    """{distribution_name: raw_specifier_string}. The specifier is kept only
    as informational context - Phase 8's dependency tree always resolves a
    transitive dependency to its own latest version rather than trying to
    satisfy the specifier (see dependency_tree.py's module docstring)."""
    deps: dict[str, str] = {}
    for req in _core_requires(requires_dist):
        match = _DEP_NAME_RE.match(req)
        if not match:
            continue
        name = match.group(1)
        deps[name] = req[match.end():].strip()
    return deps


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
        self, client: httpx.AsyncClient, package_identifier: str, version: Optional[str] = None
    ) -> dict[str, Any]:
        url = f"{PYPI_BASE}/{package_identifier}/json"
        if version is not None:
            url = f"{PYPI_BASE}/{package_identifier}/{version}/json"
        resp = await client.get(url)
        if resp.status_code == 404:
            identifier = f"{package_identifier}@{version}" if version else package_identifier
            raise PackageNotFoundError("pypi", identifier)
        resp.raise_for_status()
        return resp.json()

    async def fetch_metadata(
        self, client: httpx.AsyncClient, package_identifier: str, version: Optional[str] = None
    ) -> PackageMetadata:
        # The base (unversioned) endpoint is always fetched: it's the only
        # one carrying `releases`, the full per-version file/timestamp map
        # needed for version_count/first_published_at regardless of which
        # version is being inspected.
        data = await self._fetch_json(client, package_identifier)
        releases: dict[str, list[dict[str, Any]]] = data.get("releases") or {}
        latest_version = (data.get("info") or {}).get("version") or ""

        if version is not None and version not in releases:
            raise PackageNotFoundError("pypi", f"{package_identifier}@{version}")

        target_version = version or latest_version

        if version is not None and version != latest_version:
            # The base endpoint's `info`/`urls` always describe the *latest*
            # release - a genuinely pinned scan needs the version-specific
            # endpoint for a version's own description/license/deps/dist info.
            pinned = await self._fetch_json(client, package_identifier, version=version)
            info: dict[str, Any] = pinned.get("info") or {}
            target_files = pinned.get("urls") or []
        else:
            info = data.get("info") or {}
            target_files = releases.get(target_version) or data.get("urls") or []

        all_publish_times = [
            (v, t) for v, files in releases.items() if (t := _earliest_upload(files)) is not None
        ]
        first_published_at = min((t for _, t in all_publish_times), default=None)
        target_published_at = _earliest_upload(target_files) or (
            dict(all_publish_times).get(target_version)
        )

        requires_dist = [r for r in (info.get("requires_dist") or []) if isinstance(r, str)]

        return PackageMetadata(
            ecosystem="pypi",
            name=info.get("name") or package_identifier,
            description=info.get("summary") or None,
            latest_version=latest_version,
            version_count=len(releases),
            first_published_at=first_published_at,
            latest_published_at=target_published_at,
            license=_short_license(info.get("license")),
            homepage=info.get("home_page") or (info.get("project_urls") or {}).get("Homepage"),
            keywords=(info.get("keywords") or "").split(",") if info.get("keywords") else [],
            repository=parse_github_repository(_resolve_repo_source_url(info)),
            maintainers=[],  # not exposed historically by the API - see module docstring
            dependencies=_parse_dependencies(requires_dist),
            dependency_count=len(_core_requires(requires_dist)),
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

    async def fetch_version_history(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> list[VersionEntry]:
        data = await self._fetch_json(client, package_identifier)
        releases: dict[str, list[dict[str, Any]]] = data.get("releases") or {}
        entries = [
            VersionEntry(version=version, published_at=_earliest_upload(files))
            for version, files in releases.items()
        ]
        entries.sort(key=lambda e: e.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return entries

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
