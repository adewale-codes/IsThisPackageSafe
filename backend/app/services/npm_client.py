"""Fetches and normalizes data from the npm registry and download-counts API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx

from app.models.schemas import DownloadStats, Maintainer, PackageMetadata
from app.services.ecosystems.base import PackageNotFoundError as _PackageNotFoundError
from app.services.repo_url import parse_github_repository

REGISTRY_BASE = "https://registry.npmjs.org"
DOWNLOADS_BASE = "https://api.npmjs.org/downloads/point"

# Keys in the packument's "time" map that are not version numbers.
_TIME_META_KEYS = {"created", "modified"}


class PackageNotFoundError(_PackageNotFoundError):
    """Raised when the requested package does not exist on the npm registry.

    Subclasses the shared ecosystems.base error (so router/scanner can catch
    just that one type) while keeping this name/signature for existing
    importers (`from app.services.npm_client import PackageNotFoundError`).
    """

    def __init__(self, package_name: str):
        self.package_name = package_name
        super().__init__("npm", package_name)


async def fetch_packument(client: httpx.AsyncClient, package_name: str) -> dict[str, Any]:
    resp = await client.get(f"{REGISTRY_BASE}/{package_name}")
    if resp.status_code == 404:
        raise PackageNotFoundError(package_name)
    resp.raise_for_status()
    return resp.json()


async def fetch_downloads(
    client: httpx.AsyncClient, package_name: str, period: str = "last-month"
) -> DownloadStats:
    try:
        resp = await client.get(f"{DOWNLOADS_BASE}/{period}/{package_name}")
        if resp.status_code == 404:
            # Common for packages published very recently with no download data yet.
            return DownloadStats(period=period, downloads=0, available=False)
        resp.raise_for_status()
        data = resp.json()
        return DownloadStats(
            period=period,
            downloads=data.get("downloads", 0),
            start=data.get("start"),
            end=data.get("end"),
            available=True,
        )
    except httpx.HTTPError:
        return DownloadStats(period=period, downloads=0, available=False)


def _repository_url(repository: Any) -> Optional[str]:
    if not repository:
        return None
    if isinstance(repository, dict):
        return repository.get("url")
    if isinstance(repository, str):
        return repository
    return None


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_ordered_version_history(packument: dict[str, Any]) -> list[tuple[str, datetime]]:
    """Return (version, publish_time) tuples sorted oldest-first."""
    time_map: dict[str, str] = packument.get("time", {})
    entries = [
        (version, _parse_time(ts))
        for version, ts in time_map.items()
        if version not in _TIME_META_KEYS
    ]
    entries = [(v, t) for v, t in entries if t is not None]
    entries.sort(key=lambda pair: pair[1])
    return entries


def get_maintainers_for_version(packument: dict[str, Any], version: str) -> list[str]:
    versions: dict[str, Any] = packument.get("versions", {})
    version_data = versions.get(version, {})
    maintainers = version_data.get("maintainers", [])
    names = set()
    for m in maintainers:
        if isinstance(m, dict) and m.get("name"):
            names.add(m["name"])
        elif isinstance(m, str):
            names.add(m)
    return sorted(names)


def normalize_metadata(packument: dict[str, Any]) -> PackageMetadata:
    name = packument.get("name", "")
    dist_tags = packument.get("dist-tags", {})
    latest_version = dist_tags.get("latest", "")

    versions: dict[str, Any] = packument.get("versions", {})
    latest_data = versions.get(latest_version, {})

    time_map: dict[str, str] = packument.get("time", {})
    first_published_at = _parse_time(time_map.get("created"))
    latest_published_at = _parse_time(time_map.get(latest_version) or time_map.get("modified"))

    maintainers_raw = packument.get("maintainers", [])
    maintainers = [
        Maintainer(name=m.get("name", ""), email=m.get("email"))
        for m in maintainers_raw
        if isinstance(m, dict) and m.get("name")
    ]

    dependencies: dict[str, str] = latest_data.get("dependencies", {}) or {}

    scripts: dict[str, str] = latest_data.get("scripts", {}) or {}
    install_scripts = {
        k: v for k, v in scripts.items() if k in ("preinstall", "install", "postinstall")
    }

    dist = latest_data.get("dist", {}) or {}

    return PackageMetadata(
        ecosystem="npm",
        name=name,
        description=packument.get("description"),
        latest_version=latest_version,
        version_count=len(versions),
        first_published_at=first_published_at,
        latest_published_at=latest_published_at,
        license=latest_data.get("license") if isinstance(latest_data.get("license"), str) else None,
        homepage=packument.get("homepage"),
        keywords=packument.get("keywords", []) or [],
        repository=parse_github_repository(
            _repository_url(latest_data.get("repository") or packument.get("repository"))
        ),
        maintainers=maintainers,
        dependencies=dependencies,
        dependency_count=len(dependencies),
        install_scripts=install_scripts,
        tarball_url=dist.get("tarball"),
        tarball_shasum=dist.get("shasum"),
        unpacked_size_bytes=dist.get("unpackedSize"),
    )
