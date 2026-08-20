"""Orchestrates the full scan pipeline: fetch -> normalize -> score -> assemble."""

from __future__ import annotations

import httpx

from app.models.schemas import (
    DeepScanInfo,
    ScanResult,
    VulnerabilityCheckStatus,
    VulnerabilityFinding,
)
from app.services import deep_scan, github_client, npm_client, scoring, vuln_client

_HTTP_TIMEOUT = 10.0


async def _check_vulnerabilities_safely(
    client: httpx.AsyncClient, package_name: str, version: str
) -> tuple[list[VulnerabilityFinding], VulnerabilityCheckStatus]:
    """Never lets an OSV.dev failure crash the scan or look like a clean
    result - mirrors deep_scan.py's fail-visibly pattern (Phase 4)."""
    try:
        vulnerabilities = await vuln_client.check_vulnerabilities(client, package_name, version)
        return vulnerabilities, VulnerabilityCheckStatus(status="completed")
    except vuln_client.VulnCheckError as exc:
        return [], VulnerabilityCheckStatus(status="failed", note=str(exc))
    except Exception as exc:  # noqa: BLE001 - any failure must stay visible, never silent "clean"
        return [], VulnerabilityCheckStatus(
            status="failed", note=f"Unexpected error while checking vulnerabilities: {exc}"
        )


async def scan_package(package_name: str) -> ScanResult:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        packument = await npm_client.fetch_packument(client, package_name)
        metadata = npm_client.normalize_metadata(packument)
        downloads = await npm_client.fetch_downloads(client, package_name)
        github = await github_client.fetch_github_signals(
            client, metadata.repository.owner, metadata.repository.repo
        )
        # Run for every scan, unconditionally - unlike the deep-scan LLM
        # layer, CVE lookups are cheap and fast enough not to gate behind a
        # heuristics threshold.
        vulnerabilities, vulnerability_check = await _check_vulnerabilities_safely(
            client, package_name, metadata.latest_version
        )

    findings = scoring.run_heuristics(package_name, packument, metadata, downloads, github)
    heuristics_score = scoring.compute_score(findings)
    vulnerability_score = min(sum(v.points for v in vulnerabilities), 100)

    # Deep-scan triggering stays based on heuristics alone - a critical CVE
    # in an otherwise-legitimate package isn't a signal of malicious intent,
    # so it must not influence whether the supply-chain deep scan fires.
    would_trigger = deep_scan.should_trigger_deep_scan(heuristics_score, findings)
    deep_scan_finding = None
    deep_scan_points = 0
    if would_trigger:
        deep_scan_finding = await deep_scan.perform_deep_scan(metadata, package_name)
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
        package=package_name,
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
