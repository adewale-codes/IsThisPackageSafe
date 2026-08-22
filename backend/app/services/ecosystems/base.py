"""The EcosystemClient interface (Phase 7).

Three real implementations (npm, PyPI, Maven) exist specifically to prove
this abstraction generalizes rather than being npm with an if-statement
bolted on - npm and PyPI are both single-registry/JSON/name+version lookups,
so Maven's different coordinate system (groupId:artifactId, not a bare name)
and different metadata format (maven-metadata.xml, not JSON) is what
actually stress-tests the interface. A 4th/5th ecosystem later should be
"write one client", not an architecture rework.

Not every registry exposes every signal a scan wants (Maven has no download
counts, no per-version maintainer history, no install-scripts concept). The
contract for all of that is: return zeros/None/empty gracefully - never
fake data to fill a gap. scoring.py is responsible for treating an empty/
absent signal as "not applicable" rather than "clean", so an ecosystem with
fewer signals doesn't look artificially safer than one with more.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.models.schemas import DownloadStats, PackageMetadata, VersionEntry


class PackageNotFoundError(Exception):
    """Raised by any EcosystemClient when the package/coordinate doesn't
    exist in that ecosystem's registry. A single shared exception type so
    the router only needs one except clause regardless of ecosystem."""

    def __init__(self, ecosystem: str, package_identifier: str):
        self.ecosystem = ecosystem
        self.package_identifier = package_identifier
        super().__init__(
            f"Package '{package_identifier}' was not found in the {ecosystem} registry"
        )


class EcosystemClient(ABC):
    """One implementation per package registry. All methods are async and
    take a shared httpx.AsyncClient so scanner.py can reuse one connection
    pool across every call in a single scan, regardless of ecosystem."""

    @abstractmethod
    async def fetch_metadata(
        self, client: httpx.AsyncClient, package_identifier: str, version: Optional[str] = None
    ) -> PackageMetadata:
        """version=None resolves to latest (existing Phase 1-7 behavior).
        When a specific version is given (Phase 8), every version-sensitive
        field (dependencies, install_scripts, license, tarball info, the
        publish date) must describe *that* version, not always-latest -
        that's what makes a pinned scan actually pinned. latest_version
        stays the true current-latest regardless, as informational context.

        Raises PackageNotFoundError if the package/coordinate doesn't exist,
        or if a specific version is requested that doesn't exist for it.
        """
        raise NotImplementedError

    @abstractmethod
    async def fetch_versions(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> list[str]:
        """All known version strings, any order. Used for version-history-
        shaped heuristics; ecosystems with no such data return []."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_version_history(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> list[VersionEntry]:
        """All known versions with publish date where available (Phase 8),
        newest-first. A version whose publish date isn't obtainable is still
        included, with published_at=None - never dropped, never guessed."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_downloads(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> DownloadStats:
        """Best-effort - not every registry has this. Return
        DownloadStats(available=False) rather than fabricating a number."""
        raise NotImplementedError

    def resolve_repo_url(self, metadata: PackageMetadata) -> str | None:
        """Default implementation just reads back what fetch_metadata already
        parsed into RepositoryInfo. Override only if an ecosystem's repo URL
        needs to be derived some other way after the fact."""
        return metadata.repository.raw_url
