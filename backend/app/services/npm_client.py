"""Fetches and normalizes data from the npm registry and download-counts API."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import httpx

from app.models.schemas import DownloadStats, Maintainer, PackageMetadata, RepositoryInfo

REGISTRY_BASE = "https://registry.npmjs.org"
DOWNLOADS_BASE = "https://api.npmjs.org/downloads/point"

# Keys in the packument's "time" map that are not version numbers.
_TIME_META_KEYS = {"created", "modified"}


class PackageNotFoundError(Exception):
    """Raised when the requested package does not exist on the npm registry."""

    def __init__(self, package_name: str):
        self.package_name = package_name
        super().__init__(f"Package '{package_name}' was not found on the npm registry")


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


def _parse_repository(repository: Any) -> RepositoryInfo:
    if not repository:
        return RepositoryInfo()

    raw_url: Optional[str] = None
    if isinstance(repository, dict):
        raw_url = repository.get("url")
    elif isinstance(repository, str):
        raw_url = repository

    if not raw_url:
        return RepositoryInfo()

    cleaned = raw_url.strip()
    cleaned = re.sub(r"^git\+", "", cleaned)
    cleaned = re.sub(r"^git://", "https://", cleaned)
    cleaned = re.sub(r"^git@github\.com:", "https://github.com/", cleaned)
    cleaned = re.sub(r"\.git$", "", cleaned)

    match = re.search(r"github\.com[/:]([^/]+)/([^/#]+)", cleaned)
    if not match:
        return RepositoryInfo(raw_url=raw_url)

    owner, repo = match.group(1), match.group(2)
    return RepositoryInfo(raw_url=raw_url, owner=owner, repo=repo)


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
        name=name,
        description=packument.get("description"),
        latest_version=latest_version,
        version_count=len(versions),
        first_published_at=first_published_at,
        latest_published_at=latest_published_at,
        license=latest_data.get("license") if isinstance(latest_data.get("license"), str) else None,
        homepage=packument.get("homepage"),
        keywords=packument.get("keywords", []) or [],
        repository=_parse_repository(latest_data.get("repository") or packument.get("repository")),
        maintainers=maintainers,
        dependencies=dependencies,
        dependency_count=len(dependencies),
        install_scripts=install_scripts,
        tarball_url=dist.get("tarball"),
        unpacked_size_bytes=dist.get("unpackedSize"),
    )
