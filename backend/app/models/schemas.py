"""Pydantic models shared across the scanning pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "danger"]
Verdict = Literal["safe", "suspicious", "investigate"]


class Maintainer(BaseModel):
    name: str
    email: Optional[str] = None


class RepositoryInfo(BaseModel):
    raw_url: Optional[str] = None
    owner: Optional[str] = None
    repo: Optional[str] = None


class PackageMetadata(BaseModel):
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


class DeepScanInfo(BaseModel):
    """Placeholder describing whether Phase 4's LLM deep-scan layer would trigger."""

    would_trigger: bool
    reason: Optional[str] = None
    implemented: bool = False


class ScanResult(BaseModel):
    package: str
    resolved_version: str
    risk_score: int
    verdict: Verdict
    metadata: PackageMetadata
    downloads: DownloadStats
    github: GithubSignals
    findings: list[Finding]
    deep_scan: DeepScanInfo
