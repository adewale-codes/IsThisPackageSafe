"""npm ecosystem client - a thin adapter over the existing npm_client.py
functions, which keep their original behavior unchanged (see module
docstring in npm_client.py). scanner.py's actual npm scan path calls those
functions directly rather than through this class, to avoid fetching the
same packument twice (normalize_metadata + the maintainer-history heuristic
both need the raw packument, which this generic interface doesn't expose).
This class exists so `ecosystems.get_client("npm")` is a real, working
implementation of the shared interface for any caller that only needs the
generic surface.
"""

from __future__ import annotations

import httpx

from app.models.schemas import DownloadStats, PackageMetadata
from app.services import npm_client
from app.services.ecosystems.base import EcosystemClient, PackageNotFoundError


class NpmClient(EcosystemClient):
    async def fetch_metadata(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> PackageMetadata:
        try:
            packument = await npm_client.fetch_packument(client, package_identifier)
        except npm_client.PackageNotFoundError as exc:
            raise PackageNotFoundError("npm", package_identifier) from exc
        return npm_client.normalize_metadata(packument)

    async def fetch_versions(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> list[str]:
        try:
            packument = await npm_client.fetch_packument(client, package_identifier)
        except npm_client.PackageNotFoundError as exc:
            raise PackageNotFoundError("npm", package_identifier) from exc
        return [version for version, _ in npm_client.get_ordered_version_history(packument)]

    async def fetch_downloads(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> DownloadStats:
        return await npm_client.fetch_downloads(client, package_identifier)
