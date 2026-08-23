"""Pydantic models shared across the scanning pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "danger"]
Verdict = Literal["safe", "suspicious", "investigate"]
Ecosystem = Literal["npm", "pypi", "maven"]


class Maintainer(BaseModel):
    name: str
    email: Optional[str] = None


class RepositoryInfo(BaseModel):
    raw_url: Optional[str] = None
    owner: Optional[str] = None
    repo: Optional[str] = None


class PackageMetadata(BaseModel):
    ecosystem: Ecosystem = "npm"
    name: str
    description: Optional[str] = None
    latest_version: str
    version_count: int
    first_published_at: Optional[datetime] = None
    latest_published_at: Optional[datetime] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    repository: RepositoryInfo = Field(default_factory=RepositoryInfo)
    maintainers: list[Maintainer] = Field(default_factory=list)
    dependencies: dict[str, str] = Field(default_factory=dict)
    dependency_count: int = 0
    install_scripts: dict[str, str] = Field(default_factory=dict)
    tarball_url: Optional[str] = None
    tarball_shasum: Optional[str] = None
    unpacked_size_bytes: Optional[int] = None


class DownloadStats(BaseModel):
    period: str
    downloads: int
    start: Optional[str] = None
    end: Optional[str] = None
    available: bool = True


class GithubSignals(BaseModel):
    linked: bool = False
    owner: Optional[str] = None
    repo: Optional[str] = None
    exists: Optional[bool] = None
    archived: Optional[bool] = None
    stars: Optional[int] = None
    forks: Optional[int] = None
    open_issues: Optional[int] = None
    contributors_count: Optional[int] = None
    last_pushed_at: Optional[datetime] = None
    error: Optional[str] = None


class Finding(BaseModel):
    id: str
    label: str
    severity: Severity
    points: int
    detail: str


DeepScanStatus = Literal["completed", "failed", "skipped"]


class DeepScanFinding(BaseModel):
    """Result of the Phase 4 LLM deep-scan pass over a package's source."""

    status: DeepScanStatus
    obfuscation_detected: bool = False
    suspicious_network_calls: bool = False
    summary: str
    points: int = 0
    cached: bool = False


class DeepScanInfo(BaseModel):
    """Whether the LLM deep-scan layer triggered for this scan, and its result."""

    would_trigger: bool
    implemented: bool = True
    reason: Optional[str] = None
    finding: Optional[DeepScanFinding] = None


VulnSeverity = Literal["critical", "high", "medium", "low", "unknown"]


class VulnerabilityFinding(BaseModel):
    """A single known-vulnerability record from OSV.dev (Phase 6).

    Deliberately separate from Finding: this represents a published CVE/GHSA
    advisory against an otherwise-legitimate package, not a supply-chain/
    malicious-intent signal - the two must never be merged into one list.
    """

    id: str
    summary: str
    severity: VulnSeverity
    fixed_version: Optional[str] = None
    references: list[str] = Field(default_factory=list)
    points: int = 0


VulnCheckStatusValue = Literal["completed", "failed", "pending"]


class VulnerabilityCheckStatus(BaseModel):
    """Whether the OSV.dev lookup itself succeeded - independent of whether
    any vulnerabilities were found. Mirrors DeepScanFinding's fail-visibly
    pattern: a failed check must never look identical to a clean result.

    "pending" (Phase 9) marks a result whose vulnerability check was
    deliberately deferred to a later batch OSV lookup (see
    scanner.py's skip_vuln_check) - a transient internal state that should
    always be patched to "completed"/"failed" before a result is returned
    to any caller outside repo_scan.py's own pipeline."""

    status: VulnCheckStatusValue
    note: Optional[str] = None


class ScanResult(BaseModel):
    ecosystem: Ecosystem
    package: str
    resolved_version: str
    risk_score: int
    heuristics_score: int
    vulnerability_score: int
    verdict: Verdict
    metadata: PackageMetadata
    downloads: DownloadStats
    github: GithubSignals
    findings: list[Finding]
    deep_scan: DeepScanInfo
    vulnerabilities: list[VulnerabilityFinding]
    vulnerability_check: VulnerabilityCheckStatus


class VersionEntry(BaseModel):
    """One entry in a package's version history (Phase 8)."""

    version: str
    published_at: Optional[datetime] = None


class FlaggedDependency(BaseModel):
    """A transitive dependency (Phase 8) that came back with at least one
    Finding and/or known vulnerability from its lightweight scan (heuristics
    + OSV only - no deep-scan; see dependency_tree.py). Clean dependencies
    are never included here - only ones worth a user's attention."""

    ecosystem: Ecosystem
    package: str
    version: str
    path: list[str]
    risk_score: int
    verdict: Verdict
    findings: list[Finding]
    vulnerabilities: list[VulnerabilityFinding]


class DependencyTree(BaseModel):
    """Phase 8: root package's own full scan, plus every transitive
    dependency (recursively, up to a depth cap) that came back flagged.
    max_depth_reached / node_cap_reached tell the caller honestly whether
    the graph was fully explored or cut short by a safety guard."""

    root: ScanResult
    flagged_dependencies: list[FlaggedDependency]
    total_scanned: int
    max_depth_reached: bool
    node_cap_reached: bool


# Phase 9: repo-wide dependency scanning.


class UploadedManifest(BaseModel):
    """One manifest file's raw content, as uploaded by the CLI - the backend
    never reads a server-side filesystem path for this (see routers/repo.py);
    the CLI is what has access to the user's local repo."""

    path: str
    content: str

# How a package's scanned version was determined - a meaningful accuracy
# distinction the report is honest about, not an implementation detail to
# hide: "lockfile"/"exact" mean we know precisely what's installed, "range"
# means we picked the latest version satisfying a manifest's range (which
# may not be what's actually on disk), "unresolved" means no constraint was
# given at all and latest was used.
ResolutionMethod = Literal["lockfile", "exact", "range", "unresolved"]


class RepoManifestInfo(BaseModel):
    """One manifest file the repo scan found and parsed."""

    path: str
    ecosystem: Ecosystem
    kind: str  # "package.json", "package-lock.json", "yarn.lock", "requirements.txt", "pyproject.toml", "pom.xml"
    direct_dependency_count: int


class RepoPackageResult(BaseModel):
    """One scanned package within a repo scan - either a direct dependency
    declared in a manifest, or a transitive dependency reached by walking a
    direct dependency's own dependency graph (Phase 8's machinery)."""

    scan: ScanResult
    is_direct: bool
    pulled_in_by: Optional[str] = None  # the direct dependency's name, if transitive
    path: list[str]
    resolution_method: ResolutionMethod
    manifest_path: Optional[str] = None  # which manifest declared it, if direct


class RepoScanReport(BaseModel):
    """Phase 9: one aggregated report across every dependency (direct and
    transitive) found across every manifest in a repo. packages is ranked
    worst-first (see repo_scan.py) so the most urgent issues surface
    immediately rather than being buried in an alphabetical list."""

    manifests: list[RepoManifestInfo]
    packages: list[RepoPackageResult]
    total_scanned: int
    direct_count: int
    transitive_count: int
    flagged_count: int
    vulnerable_count: int
    vulnerability_severity_counts: dict[str, int]
    max_depth_reached: bool
    node_cap_reached: bool
