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
    verdict = scoring.compute_verdict(risk_score)

    would_trigger = deep_scan.should_trigger_deep_scan(risk_score, findings)
    deep_scan_info = DeepScanInfo(
        would_trigger=would_trigger,
        reason=(
            "Deterministic score/findings meet the deep-scan trigger threshold; "
            "LLM deep scan is not implemented until Phase 4."
            if would_trigger
            else None
        ),
        implemented=False,
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
