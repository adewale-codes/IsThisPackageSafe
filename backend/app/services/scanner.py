"""Orchestrates the full scan pipeline: fetch -> normalize -> score -> assemble."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.models.schemas import (
    DeepScanInfo,
    Ecosystem,
    PackageMetadata,
    ScanResult,
    VulnerabilityCheckStatus,
    VulnerabilityFinding,
)
from app.services import deep_scan, ecosystems, github_client, npm_client, scoring, vuln_client

_HTTP_TIMEOUT = 10.0

# OSV.dev's ecosystem strings are case-sensitive and don't match this
# project's own lowercase Ecosystem literal - verified against real queries
# during development (lowercase "pypi"/"maven" both 400).
_OSV_ECOSYSTEM: dict[Ecosystem, str] = {
    "npm": "npm",
    "pypi": "PyPI",
    "maven": "Maven",
}


async def _check_vulnerabilities_safely(
    client: httpx.AsyncClient, package_identifier: str, version: str, ecosystem: Ecosystem
) -> tuple[list[VulnerabilityFinding], VulnerabilityCheckStatus]:
    """Never lets an OSV.dev failure crash the scan or look like a clean
    result - mirrors deep_scan.py's fail-visibly pattern (Phase 4)."""
    try:
        vulnerabilities = await vuln_client.check_vulnerabilities(
            client, package_identifier, version, _OSV_ECOSYSTEM[ecosystem]
        )
        return vulnerabilities, VulnerabilityCheckStatus(status="completed")
    except vuln_client.VulnCheckError as exc:
        return [], VulnerabilityCheckStatus(status="failed", note=str(exc))
    except Exception as exc:  # noqa: BLE001 - any failure must stay visible, never silent "clean"
        return [], VulnerabilityCheckStatus(
            status="failed", note=f"Unexpected error while checking vulnerabilities: {exc}"
        )


async def _fetch_npm(
    client: httpx.AsyncClient, package_identifier: str
) -> tuple[PackageMetadata, Optional[dict[str, Any]]]:
    """npm is fetched directly (not via ecosystems.NpmClient) so the raw
    packument survives for rule_maintainer_change, which the generic
    EcosystemClient interface doesn't expose (see ecosystems/npm.py)."""
    packument = await npm_client.fetch_packument(client, package_identifier)
    metadata = npm_client.normalize_metadata(packument)
    return metadata, packument


async def scan_package(ecosystem: Ecosystem, package_identifier: str) -> ScanResult:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        packument: Optional[dict[str, Any]] = None
        if ecosystem == "npm":
            metadata, packument = await _fetch_npm(client, package_identifier)
            downloads = await npm_client.fetch_downloads(client, package_identifier)
        else:
            eco_client = ecosystems.get_client(ecosystem)
            metadata = await eco_client.fetch_metadata(client, package_identifier)
            downloads = await eco_client.fetch_downloads(client, package_identifier)

        github = await github_client.fetch_github_signals(
            client, metadata.repository.owner, metadata.repository.repo
        )
        # Run for every scan, unconditionally - unlike the deep-scan LLM
        # layer, CVE lookups are cheap and fast enough not to gate behind a
        # heuristics threshold.
        vulnerabilities, vulnerability_check = await _check_vulnerabilities_safely(
            client, package_identifier, metadata.latest_version, ecosystem
        )

    findings = scoring.run_heuristics(
        package_identifier, metadata, downloads, github, ecosystem=ecosystem, packument=packument
    )
    heuristics_score = scoring.compute_score(findings)
    vulnerability_score = min(sum(v.points for v in vulnerabilities), 100)

    # Deep-scan triggering stays based on heuristics alone - a critical CVE
    # in an otherwise-legitimate package isn't a signal of malicious intent,
    # so it must not influence whether the supply-chain deep scan fires.
    would_trigger = deep_scan.should_trigger_deep_scan(heuristics_score, findings)
    deep_scan_finding = None
    deep_scan_points = 0
    if would_trigger:
        deep_scan_finding = await deep_scan.perform_deep_scan(metadata, package_identifier)
        deep_scan_points = deep_scan_finding.points

    risk_score = min(heuristics_score + vulnerability_score + deep_scan_points, 100)
    verdict = scoring.compute_verdict(risk_score)

    deep_scan_info = DeepScanInfo(
        would_trigger=would_trigger,
        implemented=True,
        reason=(
            "Deterministic score/findings met the deep-scan trigger threshold."
            if would_trigger
            else None
        ),
        finding=deep_scan_finding,
    )

    return ScanResult(
        ecosystem=ecosystem,
        package=package_identifier,
        resolved_version=metadata.latest_version,
        risk_score=risk_score,
        heuristics_score=heuristics_score,
        vulnerability_score=vulnerability_score,
        verdict=verdict,
        metadata=metadata,
        downloads=downloads,
        github=github,
        findings=findings,
        deep_scan=deep_scan_info,
        vulnerabilities=vulnerabilities,
        vulnerability_check=vulnerability_check,
    )
