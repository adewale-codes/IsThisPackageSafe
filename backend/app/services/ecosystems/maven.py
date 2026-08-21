"""Maven Central ecosystem client - the ecosystem that actually stress-tests
the EcosystemClient interface. Unlike npm/PyPI (single-registry, JSON,
bare-name+version), Maven identifies packages by a groupId:artifactId
coordinate (not a bare name) and its canonical metadata format is XML, not
JSON. Three requests per scan:

1. Solr search (JSON) - existence check + per-version publish timestamps,
   used to derive first_published_at/latest_published_at (Maven Central's
   own maven-metadata.xml has no per-version history, only a single
   lastUpdated for the whole file).
2. maven-metadata.xml - canonical version list + <release>/<latest>. Found
   this to be more current than the search index during development (a
   freshly-published version showed up in maven-metadata.xml before it was
   reflected in Solr search results), so it - not search - is treated as
   the authoritative source for "what's the latest version".
3. The resolved latest version's POM - the only place description,
   license, SCM/homepage URL, current maintainers (<developers>), and
   dependencies live. Deliberately NOT resolved through <parent> POM
   inheritance (a real rabbit hole - some POMs, e.g. Guava's, push nearly
   all of this to a parent); a POM that inherits these fields will
   correctly show them as absent rather than guessed.

No install-scripts concept, no per-version maintainer history (so
maintainer-takeover detection is N/A here, same as PyPI and for the same
reason: the registry doesn't expose the history the heuristic needs) - but
<developers> DOES give a real *current* maintainer list, which is populated
since it's real data, not a fabrication.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.models.schemas import DownloadStats, Maintainer, PackageMetadata
from app.services.ecosystems.base import EcosystemClient, PackageNotFoundError
from app.services.repo_url import parse_github_repository

MAVEN_SEARCH_BASE = "https://search.maven.org/solrsearch/select"
MAVEN_REPO_BASE = "https://repo1.maven.org/maven2"

_POM_NS = "{http://maven.apache.org/POM/4.0.0}"

# search.maven.org's latency has been observed swinging from well under a
# second to 30s+ (occasionally timing out entirely) between one call and
# the next, from this environment - genuine, unpredictable server-side
# behavior, not a client bug (confirmed via raw, unwrapped requests during
# development). It is therefore treated as best-effort below: every call to
# it fails soft rather than raising, and maven-metadata.xml/the POM - both
# served by the much more reliable repo1.maven.org - are the authoritative
# sources for existence and version data, with search used only for the one
# signal it uniquely provides (oldest-publish timestamp).
_MAVEN_SEARCH_TIMEOUT = 10.0
_MAVEN_XML_TIMEOUT = 15.0


def split_coordinate(package_identifier: str) -> tuple[str, str]:
    """Maven's identifier format is groupId:artifactId - distinct from
    npm/PyPI's bare package name. Raises ValueError (not PackageNotFoundError)
    on malformed input; the caller maps that to a 4xx, not a 404."""
    parts = package_identifier.split(":")
    if len(parts) != 2 or not all(parts):
        raise ValueError(
            f"Maven package identifier must be 'groupId:artifactId', got {package_identifier!r}"
        )
    return parts[0], parts[1]


def _group_path(group_id: str) -> str:
    return group_id.replace(".", "/")


def _parse_maven_timestamp(value: Optional[str]) -> Optional[datetime]:
    """maven-metadata.xml's <lastUpdated> is YYYYMMDDHHMMSS, UTC."""
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _pom_find(element: ET.Element, path: str) -> Optional[ET.Element]:
    """POMs almost always declare the modelVersion 4.0.0 namespace, but a
    few nonstandard ones omit it - try namespaced lookup first, then bare."""
    namespaced = "/".join(f"{_POM_NS}{part}" for part in path.split("/"))
    found = element.find(namespaced)
    if found is not None:
        return found
    return element.find(path)


def _pom_findall(element: ET.Element, path: str) -> list[ET.Element]:
    namespaced = "/".join(f"{_POM_NS}{part}" for part in path.split("/"))
    found = element.findall(namespaced)
    if found:
        return found
    return element.findall(path)


def _pom_text(element: ET.Element, path: str) -> Optional[str]:
    found = _pom_find(element, path)
    if found is None or found.text is None:
        return None
    text = " ".join(found.text.split())  # collapse whitespace/newlines in e.g. <description>
    return text or None


class MavenClient(EcosystemClient):
    async def _search(
        self, client: httpx.AsyncClient, group_id: str, artifact_id: str, *, sort: Optional[str] = None
    ) -> tuple[list[dict], int]:
        """Best-effort. Fails soft (empty docs, numFound=0) on any HTTP error
        or timeout rather than raising - callers must not distinguish
        "confirmed zero matches" from "search didn't answer in time", since
        maven-metadata.xml is the authoritative existence/version source
        anyway (see module docstring)."""
        params = {
            "q": f"g:{group_id} AND a:{artifact_id}",
            "core": "gav",
            "rows": 20,  # a large rows value (tried 200) made search.maven.org time out
            "wt": "json",
        }
        if sort:
            params["sort"] = sort
        try:
            resp = await client.get(MAVEN_SEARCH_BASE, params=params, timeout=_MAVEN_SEARCH_TIMEOUT)
            resp.raise_for_status()
        except httpx.HTTPError:
            return [], 0
        response = resp.json().get("response") or {}
        return response.get("docs") or [], response.get("numFound", 0)

    async def _latest_search_doc(
        self, client: httpx.AsyncClient, group_id: str, artifact_id: str
    ) -> tuple[Optional[dict], int]:
        """Default sort (score desc, timestamp desc) - docs[0], if any, is
        the most-recently-published match. Also doubles as the existence
        check via numFound."""
        docs, num_found = await self._search(client, group_id, artifact_id)
        return (docs[0] if docs else None), num_found

    async def _oldest_published_at(
        self, client: httpx.AsyncClient, group_id: str, artifact_id: str
    ) -> Optional[datetime]:
        """rows=1 sorted ascending by timestamp returns exactly the single
        oldest published version in one cheap call - no need to page
        through full version history just to find the minimum."""
        docs, _ = await self._search(client, group_id, artifact_id, sort="timestamp asc")
        if not docs:
            return None
        ts = docs[0].get("timestamp")
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if isinstance(ts, (int, float)) else None

    async def _fetch_metadata_xml(
        self, client: httpx.AsyncClient, group_id: str, artifact_id: str
    ) -> Optional[ET.Element]:
        """repo1.maven.org has been reliably fast in testing (unlike
        search.maven.org), but a timeout here is treated the same as a 404 -
        both mean "no version data available from this source", and the
        caller already has a fallback (search) for that case."""
        url = f"{MAVEN_REPO_BASE}/{_group_path(group_id)}/{artifact_id}/maven-metadata.xml"
        try:
            resp = await client.get(url, timeout=_MAVEN_XML_TIMEOUT)
        except httpx.HTTPError:
            return None
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return ET.fromstring(resp.text)

    async def _fetch_pom(
        self, client: httpx.AsyncClient, group_id: str, artifact_id: str, version: str
    ) -> Optional[ET.Element]:
        url = (
            f"{MAVEN_REPO_BASE}/{_group_path(group_id)}/{artifact_id}/{version}/"
            f"{artifact_id}-{version}.pom"
        )
        try:
            resp = await client.get(url, timeout=_MAVEN_XML_TIMEOUT)
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        try:
            return ET.fromstring(resp.text)
        except ET.ParseError:
            return None

    async def fetch_metadata(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> PackageMetadata:
        group_id, artifact_id = split_coordinate(package_identifier)

        # maven-metadata.xml (repo1.maven.org) fetched first and treated as
        # the primary existence/version source, since it's reliably fast.
        # The search existence-check round-trip is skipped entirely once
        # metadata.xml has already answered - it's only needed as a fallback
        # for a package so new metadata.xml hasn't been regenerated yet, and
        # skipping it avoids paying search's (occasionally 20s+) latency on
        # every scan of an existing package.
        metadata_xml = await self._fetch_metadata_xml(client, group_id, artifact_id)

        search_doc: Optional[dict] = None
        num_found = 0
        if metadata_xml is None:
            search_doc, num_found = await self._latest_search_doc(client, group_id, artifact_id)

        if num_found == 0 and metadata_xml is None:
            raise PackageNotFoundError("maven", package_identifier)

        versions: list[str] = []
        latest_version = ""
        latest_published_at: Optional[datetime] = None

        if metadata_xml is not None:
            versioning = metadata_xml.find("versioning")
            if versioning is not None:
                versions = [v.text for v in versioning.findall("versions/version") if v.text]
                latest_version = (
                    (versioning.findtext("release") or "").strip()
                    or (versioning.findtext("latest") or "").strip()
                )
                latest_published_at = _parse_maven_timestamp(versioning.findtext("lastUpdated"))

        if not latest_version and search_doc:
            latest_version = search_doc.get("v", "")
        if not versions and latest_version:
            versions = [latest_version]
        if latest_published_at is None and search_doc:
            ts = search_doc.get("timestamp")
            if isinstance(ts, (int, float)):
                latest_published_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

        if not latest_version:
            raise PackageNotFoundError("maven", package_identifier)

        first_published_at = await self._oldest_published_at(client, group_id, artifact_id)

        pom = await self._fetch_pom(client, group_id, artifact_id, latest_version)

        description = homepage = license_name = repo_source_url = None
        maintainers: list[Maintainer] = []
        dependency_count = 0

        if pom is not None:
            description = _pom_text(pom, "description")
            homepage = _pom_text(pom, "url")
            license_name = _pom_text(pom, "licenses/license/name")
            repo_source_url = _pom_text(pom, "scm/url") or homepage

            maintainers = [
                Maintainer(
                    name=_pom_text(dev, "name") or _pom_text(dev, "id") or "unknown",
                    email=_pom_text(dev, "email"),
                )
                for dev in _pom_findall(pom, "developers/developer")
            ]

            dependency_count = sum(
                1
                for dep in _pom_findall(pom, "dependencies/dependency")
                if (_pom_text(dep, "scope") or "compile") != "test"
            )

        return PackageMetadata(
            ecosystem="maven",
            name=package_identifier,
            description=description,
            latest_version=latest_version,
            version_count=len(versions) or 1,
            first_published_at=first_published_at,
            latest_published_at=latest_published_at,
            license=license_name,
            homepage=homepage,
            keywords=[],
            repository=parse_github_repository(repo_source_url),
            maintainers=maintainers,
            dependencies={},  # POM deps carry groupId:artifactId, not name:version - see dependency_count
            dependency_count=dependency_count,
            install_scripts={},  # N/A for Maven - see module docstring
            tarball_url=None,  # deliberately not wired to Phase 4 deep-scan this phase (JAR, not tarball)
            tarball_shasum=None,
            unpacked_size_bytes=None,
        )

    async def fetch_versions(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> list[str]:
        group_id, artifact_id = split_coordinate(package_identifier)
        metadata_xml = await self._fetch_metadata_xml(client, group_id, artifact_id)
        if metadata_xml is not None:
            versioning = metadata_xml.find("versioning")
            if versioning is not None:
                versions = [v.text for v in versioning.findall("versions/version") if v.text]
                if versions:
                    return versions
        search_doc, _ = await self._latest_search_doc(client, group_id, artifact_id)
        return [search_doc["v"]] if search_doc and "v" in search_doc else []

    async def fetch_downloads(
        self, client: httpx.AsyncClient, package_identifier: str
    ) -> DownloadStats:
        # Maven Central has no download-count API at all - no best-effort
        # fallback exists here, unlike PyPI's pypistats.org. Return the
        # "not available" shape rather than a fabricated number.
        return DownloadStats(period="last-month", downloads=0, available=False)
