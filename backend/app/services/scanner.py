"""Orchestrates the full scan pipeline: fetch -> normalize -> score -> assemble."""

from __future__ import annotations

import httpx

from app.models.schemas import DeepScanInfo, ScanResult
from app.services import deep_scan, github_client, npm_client, scoring

_HTTP_TIMEOUT = 10.0


async def scan_package(package_name: str) -> ScanResult:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        packument = await npm_client.fetch_packument(client, package_name)
        metadata = npm_client.normalize_metadata(packument)
        downloads = await npm_client.fetch_downloads(client, package_name)
        github = await github_client.fetch_github_signals(
            client, metadata.repository.owner, metadata.repository.repo
        )

    findings = scoring.run_heuristics(package_name, packument, metadata, downloads, github)
    risk_score = scoring.compute_score(findings)

    would_trigger = deep_scan.should_trigger_deep_scan(risk_score, findings)
    deep_scan_finding = None
    if would_trigger:
        deep_scan_finding = await deep_scan.perform_deep_scan(metadata, package_name)
        risk_score = min(risk_score + deep_scan_finding.points, 100)

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
        verdict=verdict,
        metadata=metadata,
        downloads=downloads,
        github=github,
        findings=findings,
        deep_scan=deep_scan_info,
    )
