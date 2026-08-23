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
    client: httpx.AsyncClient, package_identifier: str, version: Optional[str] = None
) -> tuple[PackageMetadata, Optional[dict[str, Any]]]:
    """npm is fetched directly (not via ecosystems.NpmClient) so the raw
    packument survives for rule_maintainer_change, which the generic
    EcosystemClient interface doesn't expose (see ecosystems/npm.py)."""
    packument = await npm_client.fetch_packument(client, package_identifier)
    metadata = npm_client.normalize_metadata(packument, version)
    return metadata, packument


async def _scan_with_client(
    client: httpx.AsyncClient,
    ecosystem: Ecosystem,
    package_identifier: str,
    version: Optional[str] = None,
    *,
    enable_deep_scan: bool = True,
    skip_vuln_check: bool = False,
) -> ScanResult:
    """The actual orchestration, over a caller-supplied httpx.AsyncClient so
    a Phase 8 dependency-tree build can share one connection pool across
    every node instead of opening a new client per package. scan_package()
    below is the single-scan entry point that owns its own client; this is
    also what dependency_tree.py calls directly for each node.

    skip_vuln_check exists for Phase 9's repo scanner: checking OSV.dev one
    package at a time doesn't scale to a repo's full dependency count, so
    repo_scan.py instead batches every package's vulnerability lookup into
    one (or a few) check_vulnerabilities_batch() calls after every node has
    been scanned, then patches the real result in via _apply_vulnerabilities
    below. A skipped check is marked "pending", never "completed" - it must
    never be mistaken for a real clean result if something goes wrong before
    the patch happens."""
    packument: Optional[dict[str, Any]] = None
    if ecosystem == "npm":
        metadata, packument = await _fetch_npm(client, package_identifier, version)
        downloads = await npm_client.fetch_downloads(client, package_identifier)
    else:
        eco_client = ecosystems.get_client(ecosystem)
        metadata = await eco_client.fetch_metadata(client, package_identifier, version)
        downloads = await eco_client.fetch_downloads(client, package_identifier)

    # The actual version being inspected - metadata.latest_version stays the
    # true current-latest for reference even on a pinned scan (Phase 8), so
    # every version-sensitive use (OSV lookup, the reported result) must use
    # this, not metadata.latest_version.
    resolved_version = version or metadata.latest_version

    github = await github_client.fetch_github_signals(
        client, metadata.repository.owner, metadata.repository.repo
    )
    if skip_vuln_check:
        vulnerabilities, vulnerability_check = [], VulnerabilityCheckStatus(status="pending")
    else:
        # Run for every scan, unconditionally - unlike the deep-scan LLM
        # layer, CVE lookups are cheap and fast enough not to gate behind a
        # heuristics threshold.
        vulnerabilities, vulnerability_check = await _check_vulnerabilities_safely(
            client, package_identifier, resolved_version, ecosystem
        )

    findings = scoring.run_heuristics(
        package_identifier, metadata, downloads, github, ecosystem=ecosystem, packument=packument
    )
    heuristics_score = scoring.compute_score(findings)
    vulnerability_score = min(sum(v.points for v in vulnerabilities), 100)

    # Deep-scan triggering stays based on heuristics alone - a critical CVE
    # in an otherwise-legitimate package isn't a signal of malicious intent,
    # so it must not influence whether the supply-chain deep scan fires.
    # would_trigger reflects the deterministic signal regardless of
    # enable_deep_scan, so a transitive dependency (Phase 8, deep-scan
    # deliberately skipped - see dependency_tree.py) can still honestly
    # report "this would have warranted a deep scan" without actually
    # running the LLM call for it.
    would_trigger = deep_scan.should_trigger_deep_scan(heuristics_score, findings)
    deep_scan_finding = None
    deep_scan_points = 0
    if enable_deep_scan and would_trigger:
        deep_scan_finding = await deep_scan.perform_deep_scan(
            metadata, package_identifier, http_client=client
        )
        deep_scan_points = deep_scan_finding.points

    risk_score = min(heuristics_score + vulnerability_score + deep_scan_points, 100)
    verdict = scoring.compute_verdict(risk_score)

    if would_trigger and not enable_deep_scan:
        reason = (
            "Heuristics met the deep-scan trigger threshold, but deep scan is skipped for "
            "transitive dependency scans (Phase 8)."
        )
    elif would_trigger:
        reason = "Deterministic score/findings met the deep-scan trigger threshold."
    else:
        reason = None

    deep_scan_info = DeepScanInfo(
        would_trigger=would_trigger and enable_deep_scan,
        implemented=True,
        reason=reason,
        finding=deep_scan_finding,
    )

    return ScanResult(
        ecosystem=ecosystem,
        package=package_identifier,
        resolved_version=resolved_version,
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


async def scan_package(
    ecosystem: Ecosystem, package_identifier: str, version: Optional[str] = None
) -> ScanResult:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        return await _scan_with_client(client, ecosystem, package_identifier, version)


def apply_vulnerabilities(
    result: ScanResult,
    vulnerabilities: list[VulnerabilityFinding],
    check: VulnerabilityCheckStatus,
) -> ScanResult:
    """Phase 9: patches a skip_vuln_check=True result with the real
    vulnerability data (from a batch OSV lookup) and recomputes every score
    field that depends on it - vulnerability_score, risk_score, and verdict
    all need to reflect the patched-in data, not the empty placeholder the
    scan itself produced."""
    vulnerability_score = min(sum(v.points for v in vulnerabilities), 100)
    deep_scan_points = result.deep_scan.finding.points if result.deep_scan.finding else 0
    risk_score = min(result.heuristics_score + vulnerability_score + deep_scan_points, 100)
    verdict = scoring.compute_verdict(risk_score)
    return result.model_copy(
        update={
            "vulnerabilities": vulnerabilities,
            "vulnerability_check": check,
            "vulnerability_score": vulnerability_score,
            "risk_score": risk_score,
            "verdict": verdict,
        }
    )
