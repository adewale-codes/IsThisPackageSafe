"""Phase 9: repo-wide dependency scanning - the assembly phase.

Takes a set of uploaded manifest file contents (see routers/repo.py for why
raw content, not a server-side path), parses+resolves every direct
dependency they declare, walks each one's transitive graph (reusing Phase
8's dependency_tree.py machinery), and produces one aggregated,
worst-first-ranked RepoScanReport.

Two things this phase specifically wires in that earlier phases built but
didn't use yet:

- Batch OSV lookups (check_vulnerabilities_batch, built in Phase 6, never
  called until now). Every package scanned here uses
  scanner._scan_with_client(..., skip_vuln_check=True) - vulnerabilities are
  deliberately left empty ("pending") during the scan/walk phase, then
  filled in for everyone at once via one batch call per ecosystem at the
  end (_apply_batch_vulnerabilities). This is why a repo scan doesn't cost
  one OSV round-trip per package.
- One memoization scope across the *whole* repo scan, not one per direct
  dependency. Every direct dependency (from every manifest) and every node
  reached while walking any of their transitive graphs shares a single
  dependency_tree._TreeState - so a package that's a direct dependency in
  one manifest and also a transitive dependency three levels under a
  different manifest's direct dependency is still scanned exactly once,
  the same guarantee Phase 8 already makes within a single package's tree.
"""

from __future__ import annotations

import asyncio
import posixpath
from dataclasses import dataclass
from typing import Optional

import httpx

from app.models.schemas import (
    Ecosystem,
    RepoManifestInfo,
    RepoPackageResult,
    RepoScanReport,
    ResolutionMethod,
    ScanResult,
    UploadedManifest,
    VulnerabilityCheckStatus,
    VulnerabilityFinding,
)
from app.services import dependency_tree, ecosystems, manifest, scanner, version_resolve, vuln_client

_KIND_BY_BASENAME: dict[str, tuple[Ecosystem, str]] = {
    "package.json": ("npm", "package.json"),
    "package-lock.json": ("npm", "package-lock.json"),
    "yarn.lock": ("npm", "yarn.lock"),
    "requirements.txt": ("pypi", "requirements.txt"),
    "pyproject.toml": ("pypi", "pyproject.toml"),
    "pom.xml": ("maven", "pom.xml"),
}

# OSV.dev's batch endpoint caps at 1000 queries per request (Phase 6).
_OSV_BATCH_CHUNK = 1000


class NoManifestsFoundError(Exception):
    """Raised when none of the uploaded files match a recognized manifest
    filename - the CLI's own local discovery should normally prevent this,
    but the check stays here too since this endpoint takes arbitrary
    uploaded content, not a trusted local walk."""


@dataclass
class _ResolvedDirect:
    ecosystem: Ecosystem
    name: str
    version: Optional[str]
    resolution_method: ResolutionMethod
    manifest_path: str


@dataclass
class _ProvenanceEntry:
    is_direct: bool
    pulled_in_by: Optional[str]
    path: list[str]
    resolution_method: ResolutionMethod
    manifest_path: Optional[str]
    result: ScanResult


def _classify(path: str) -> Optional[tuple[Ecosystem, str]]:
    basename = posixpath.basename(path.replace("\\", "/"))
    return _KIND_BY_BASENAME.get(basename)


def _dirname(path: str) -> str:
    return posixpath.dirname(path.replace("\\", "/"))


async def _resolve_npm_manifest(
    client: httpx.AsyncClient,
    package_json: UploadedManifest,
    lockfile: Optional[tuple[UploadedManifest, str]],  # (file, "package-lock.json" | "yarn.lock")
) -> tuple[list[_ResolvedDirect], int]:
    specs = manifest.parse_package_json(package_json.content, package_json.path)
    if not specs:
        return [], 0

    lockfile_versions: dict[str, str] = {}
    if lockfile is not None:
        lock_file, lock_kind = lockfile
        names = {s.name for s in specs}
        try:
            if lock_kind == "package-lock.json":
                lockfile_versions = manifest.resolve_npm_lockfile_versions(lock_file.content, names)
            else:
                lockfile_versions = manifest.resolve_yarn_lock_versions(lock_file.content, names)
        except Exception:  # noqa: BLE001 - a malformed lockfile falls back to range resolution
            lockfile_versions = {}

    npm_client = ecosystems.get_client("npm")
    resolved: list[_ResolvedDirect] = []
    for spec in specs:
        if spec.name in lockfile_versions:
            resolved.append(
                _ResolvedDirect("npm", spec.name, lockfile_versions[spec.name], "lockfile", package_json.path)
            )
            continue

        version = None
        method: ResolutionMethod = "unresolved"
        if spec.version_constraint:
            try:
                versions = await npm_client.fetch_versions(client, spec.name)
                match = version_resolve.npm_max_satisfying(versions, spec.version_constraint)
                if match:
                    version, method = match, "range"
            except ecosystems.PackageNotFoundError:
                continue
        resolved.append(_ResolvedDirect("npm", spec.name, version, method, package_json.path))

    return resolved, len(specs)


async def _resolve_python_manifest(
    client: httpx.AsyncClient, file: UploadedManifest, kind: str
) -> tuple[list[_ResolvedDirect], int]:
    if kind == "requirements.txt":
        specs = manifest.parse_requirements_txt(file.content, file.path)
    else:
        specs = manifest.parse_pyproject_toml(file.content, file.path)
    if not specs:
        return [], 0

    pypi_client = ecosystems.get_client("pypi")
    resolved: list[_ResolvedDirect] = []
    for spec in specs:
        if spec.resolution_method == "exact":
            resolved.append(_ResolvedDirect("pypi", spec.name, spec.version_constraint, "exact", file.path))
            continue

        version = None
        method: ResolutionMethod = "unresolved"
        if spec.version_constraint:
            try:
                versions = await pypi_client.fetch_versions(client, spec.name)
                match = version_resolve.python_max_satisfying(versions, spec.version_constraint)
                if match:
                    version, method = match, "range"
            except ecosystems.PackageNotFoundError:
                continue
        resolved.append(_ResolvedDirect("pypi", spec.name, version, method, file.path))

    return resolved, len(specs)


async def _resolve_maven_manifest(file: UploadedManifest) -> tuple[list[_ResolvedDirect], int]:
    specs = manifest.parse_pom_xml(file.content, file.path)
    resolved = [
        _ResolvedDirect("maven", spec.name, spec.version_constraint, spec.resolution_method, file.path)
        for spec in specs
    ]
    return resolved, len(specs)


async def _resolve_all_manifests(
    client: httpx.AsyncClient, files: list[UploadedManifest]
) -> tuple[list[_ResolvedDirect], list[RepoManifestInfo]]:
    by_dir_npm: dict[str, dict[str, UploadedManifest]] = {}
    python_files: list[UploadedManifest] = []
    maven_files: list[UploadedManifest] = []
    kinds_by_path: dict[str, str] = {}

    for f in files:
        classified = _classify(f.path)
        if classified is None:
            continue
        eco, kind = classified
        kinds_by_path[f.path] = kind
        if eco == "npm":
            by_dir_npm.setdefault(_dirname(f.path), {})[kind] = f
        elif eco == "pypi":
            python_files.append(f)
        elif eco == "maven":
            maven_files.append(f)

    direct: list[_ResolvedDirect] = []
    manifest_infos: list[RepoManifestInfo] = []

    for group in by_dir_npm.values():
        package_json = group.get("package.json")
        if package_json is None:
            continue
        lockfile = None
        if "package-lock.json" in group:
            lockfile = (group["package-lock.json"], "package-lock.json")
        elif "yarn.lock" in group:
            lockfile = (group["yarn.lock"], "yarn.lock")
        resolved, count = await _resolve_npm_manifest(client, package_json, lockfile)
        direct.extend(resolved)
        manifest_infos.append(
            RepoManifestInfo(path=package_json.path, ecosystem="npm", kind="package.json", direct_dependency_count=count)
        )
        if lockfile is not None:
            manifest_infos.append(
                RepoManifestInfo(path=lockfile[0].path, ecosystem="npm", kind=lockfile[1], direct_dependency_count=0)
            )

    for f in python_files:
        kind = kinds_by_path[f.path]
        resolved, count = await _resolve_python_manifest(client, f, kind)
        direct.extend(resolved)
        manifest_infos.append(RepoManifestInfo(path=f.path, ecosystem="pypi", kind=kind, direct_dependency_count=count))

    for f in maven_files:
        resolved, count = await _resolve_maven_manifest(f)
        direct.extend(resolved)
        manifest_infos.append(RepoManifestInfo(path=f.path, ecosystem="maven", kind="pom.xml", direct_dependency_count=count))

    return direct, manifest_infos


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def _apply_batch_vulnerabilities(
    client: httpx.AsyncClient, provenance: dict[tuple[str, str], _ProvenanceEntry]
) -> None:
    """Patches every scanned package's real vulnerability data in, one
    check_vulnerabilities_batch() call per ecosystem (batched further into
    chunks of <=1000, OSV's own per-request cap) - not one query per
    package. Mutates `provenance` in place."""
    by_ecosystem: dict[Ecosystem, list[tuple[str, str]]] = {}
    for (eco, _key), entry in provenance.items():
        by_ecosystem.setdefault(eco, []).append((entry.result.package, entry.result.resolved_version))  # type: ignore[arg-type]

    for eco, pairs in by_ecosystem.items():
        osv_ecosystem = scanner._OSV_ECOSYSTEM[eco]
        batch_map: dict[tuple[str, str], list[VulnerabilityFinding]] = {}
        check = VulnerabilityCheckStatus(status="completed")

        try:
            for chunk in _chunked(pairs, _OSV_BATCH_CHUNK):
                queries = [(name, version, osv_ecosystem) for name, version in chunk]
                batch_map.update(await vuln_client.check_vulnerabilities_batch(client, queries))
        except vuln_client.VulnCheckError as exc:
            check = VulnerabilityCheckStatus(status="failed", note=str(exc))
        except Exception as exc:  # noqa: BLE001 - a batch failure must stay visible, never silent-clean
            check = VulnerabilityCheckStatus(
                status="failed", note=f"Unexpected error during batch vulnerability check: {exc}"
            )

        for key, entry in provenance.items():
            if key[0] != eco:
                continue
            vulns = [] if check.status == "failed" else batch_map.get(
                (entry.result.package, entry.result.resolved_version), []
            )
            entry.result = scanner.apply_vulnerabilities(entry.result, vulns, check)


_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}


async def scan_repo(
    uploaded_manifests: list[UploadedManifest],
    *,
    max_depth: int = dependency_tree.DEFAULT_MAX_DEPTH,
    node_cap: int = dependency_tree.DEFAULT_NODE_CAP,
) -> RepoScanReport:
    async with httpx.AsyncClient(timeout=scanner._HTTP_TIMEOUT) as client:
        direct_specs, manifest_infos = await _resolve_all_manifests(client, uploaded_manifests)
        if not manifest_infos:
            raise NoManifestsFoundError(
                "No recognized manifest files were found (looked for package.json, "
                "requirements.txt, pyproject.toml, pom.xml)."
            )

        # Dedupe direct deps across manifests by (ecosystem, name) - first
        # manifest to declare a package wins if two disagree on version
        # (rare in a healthy repo; not worth a full conflict-reconciliation
        # pass for this phase).
        deduped: dict[tuple[str, str], _ResolvedDirect] = {}
        for dep in direct_specs:
            key = (dep.ecosystem, dep.name.lower())
            deduped.setdefault(key, dep)

        state = dependency_tree._TreeState(node_cap=node_cap)

        # Seed every direct dependency into the shared memo up front - like
        # Phase 8's tree root, direct dependencies are always scanned in
        # full regardless of node_cap (the cap protects the *transitive*
        # exploration beneath them, not the packages the repo's own
        # manifests actually declare).
        for key, dep in deduped.items():
            state.memo[key] = asyncio.ensure_future(
                dependency_tree._scan_dependency(
                    client, dep.ecosystem, dep.name, dep.version, skip_vuln_check=True
                )
            )

        provenance: dict[tuple[str, str], _ProvenanceEntry] = {}
        direct_results: dict[tuple[str, str], Optional[ScanResult]] = {}
        for key, dep in deduped.items():
            result = await state.memo[key]
            direct_results[key] = result
            if result is not None:
                provenance[key] = _ProvenanceEntry(
                    is_direct=True,
                    pulled_in_by=None,
                    path=[dep.name],
                    resolution_method=dep.resolution_method,
                    manifest_path=dep.manifest_path,
                    result=result,
                )

        def _make_on_visit(direct_name: str):
            def on_visit(name: str, result: ScanResult, path: list[str]) -> None:
                key = (result.ecosystem, name.lower())
                if key not in provenance:
                    provenance[key] = _ProvenanceEntry(
                        is_direct=False,
                        pulled_in_by=direct_name,
                        path=path,
                        resolution_method="unresolved",
                        manifest_path=None,
                        result=result,
                    )

            return on_visit

        walk_calls = []
        for key, dep in deduped.items():
            result = direct_results.get(key)
            if result is None:
                continue
            children = dependency_tree._dependency_names(result)
            on_visit = _make_on_visit(dep.name)
            walk_calls.extend(
                dependency_tree._walk(
                    client, dep.ecosystem, child, 1, [dep.name], max_depth, state,
                    skip_vuln_check=True, on_visit=on_visit,
                )
                for child in children
            )
        if walk_calls:
            await asyncio.gather(*walk_calls)

        await _apply_batch_vulnerabilities(client, provenance)

        packages = [
            RepoPackageResult(
                scan=entry.result,
                is_direct=entry.is_direct,
                pulled_in_by=entry.pulled_in_by,
                path=entry.path,
                resolution_method=entry.resolution_method,
                manifest_path=entry.manifest_path,
            )
            for entry in provenance.values()
        ]
        packages.sort(key=lambda p: (-p.scan.risk_score, p.scan.package.lower()))

        direct_count = sum(1 for p in packages if p.is_direct)
        flagged_count = sum(1 for p in packages if p.scan.findings)
        vulnerable_count = sum(1 for p in packages if p.scan.vulnerabilities)

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        for p in packages:
            if not p.scan.vulnerabilities:
                continue
            worst = max(p.scan.vulnerabilities, key=lambda v: _SEVERITY_RANK[v.severity])
            severity_counts[worst.severity] += 1

        return RepoScanReport(
            manifests=manifest_infos,
            packages=packages,
            total_scanned=len(packages),
            direct_count=direct_count,
            transitive_count=len(packages) - direct_count,
            flagged_count=flagged_count,
            vulnerable_count=vulnerable_count,
            vulnerability_severity_counts=severity_counts,
            max_depth_reached=state.max_depth_reached,
            node_cap_reached=state.node_cap_reached,
        )
