"""Known-vulnerability lookups against OSV.dev (Phase 6).

This is a second, independent signal from the supply-chain heuristics in
scoring.py: it answers "does this exact package version have a published
CVE/GHSA advisory", not "does this package behave maliciously". Callers must
keep the two separate (see VulnerabilityFinding vs. Finding in schemas.py).

OSV.dev requires no auth and documents no rate limit, but we still batch
where possible to be a good citizen - check_vulnerabilities() covers the
single-package case scanner.py needs today; check_vulnerabilities_batch()
covers the bulk case Phase 9's repo scanning will need, built now so that
future work doesn't need a client rewrite.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import httpx

from app.models.schemas import VulnerabilityFinding, VulnSeverity

OSV_API_BASE = "https://api.osv.dev/v1"
_OSV_TIMEOUT = 10.0

_SEVERITY_POINTS: dict[VulnSeverity, int] = {
    "critical": 40,
    "high": 25,
    "medium": 12,
    "low": 5,
    "unknown": 3,
}

# GHSA (the dominant source for npm advisories) uses "MODERATE" rather than
# "MEDIUM" for database_specific.severity; accept both spellings.
_SEVERITY_STRING_MAP: dict[str, VulnSeverity] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MODERATE": "medium",
    "MEDIUM": "medium",
    "LOW": "low",
}

# CVSS v3.0/v3.1 base-score metric weights, per the published FIRST.org spec.
_CVSS_V3_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_CVSS_V3_AC = {"L": 0.77, "H": 0.44}
_CVSS_V3_UI = {"N": 0.85, "R": 0.62}
_CVSS_V3_CIA = {"N": 0.0, "L": 0.22, "H": 0.56}
_CVSS_V3_PR = {
    "U": {"N": 0.85, "L": 0.62, "H": 0.27},
    "C": {"N": 0.85, "L": 0.68, "H": 0.50},
}


class VulnCheckError(Exception):
    """Raised when the OSV.dev API call fails, times out, or returns an
    unparseable response - never silently swallowed into an empty result,
    so the caller can surface a visible "check didn't complete" note rather
    than a false-negative-looking empty vulnerability list."""


def _cvss_roundup(value: float) -> float:
    """The CVSS spec's official 'Roundup' function: round up to one decimal
    place, expressed with 5-digit integer precision to avoid float drift."""
    int_input = round(value * 100000)
    if int_input % 10000 == 0:
        return int_input / 100000
    return (math.floor(int_input / 10000) + 1) / 10


def _cvss_v3_base_score(vector: str) -> Optional[float]:
    """Compute the CVSS v3.0/3.1 base score from a full vector string (e.g.
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"). Returns None if the
    vector is malformed or missing a required metric. CVSS v2 and v4 vectors
    are not parsed here (v4 uses a large lookup table, not a formula) - they
    fall through to the database_specific.severity string when available,
    else "unknown".
    """
    try:
        parts = dict(segment.split(":", 1) for segment in vector.split("/") if ":" in segment)
        av = _CVSS_V3_AV[parts["AV"]]
        ac = _CVSS_V3_AC[parts["AC"]]
        ui = _CVSS_V3_UI[parts["UI"]]
        scope = parts["S"]
        pr = _CVSS_V3_PR[scope][parts["PR"]]
        c = _CVSS_V3_CIA[parts["C"]]
        i = _CVSS_V3_CIA[parts["I"]]
        a = _CVSS_V3_CIA[parts["A"]]
    except (KeyError, ValueError):
        return None

    iss = 1 - ((1 - c) * (1 - i) * (1 - a))
    impact = 6.42 * iss if scope == "U" else 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    exploitability = 8.22 * av * ac * pr * ui

    if impact <= 0:
        return 0.0
    if scope == "U":
        return _cvss_roundup(min(impact + exploitability, 10.0))
    return _cvss_roundup(min(1.08 * (impact + exploitability), 10.0))


def _score_to_numeric(score_value: str) -> Optional[float]:
    score_value = score_value.strip()
    try:
        return float(score_value)
    except ValueError:
        pass
    if score_value.upper().startswith("CVSS:3"):
        return _cvss_v3_base_score(score_value)
    return None


def _severity_from_cvss_score(score: float) -> VulnSeverity:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "unknown"


def _severity_from_string(value: Any) -> Optional[VulnSeverity]:
    if not isinstance(value, str) or not value.strip():
        return None
    return _SEVERITY_STRING_MAP.get(value.strip().upper())


def resolve_severity(vuln: dict[str, Any]) -> VulnSeverity:
    """Pick the highest-confidence severity signal available in an OSV
    record. OSV's schema varies by source database, so this checks each
    known shape in order of reliability and falls back to "unknown" rather
    than ever guessing "low" for missing data."""

    # 1. Top-level database_specific.severity - a plain string ("HIGH", etc),
    #    the most direct signal, common on GHSA-sourced npm advisories.
    direct = _severity_from_string((vuln.get("database_specific") or {}).get("severity"))
    if direct:
        return direct

    # 2. Same field, but nested per-affected-entry instead of top-level.
    for affected in vuln.get("affected", []) or []:
        direct = _severity_from_string((affected.get("database_specific") or {}).get("severity"))
        if direct:
            return direct

    # 3. CVSS vectors/scores under the top-level `severity` array. Take the
    #    highest score found across all entries (a record can carry both a
    #    v2 and v3 vector; only v3 is computed here - see _cvss_v3_base_score).
    best_score: Optional[float] = None
    for entry in vuln.get("severity", []) or []:
        score_value = entry.get("score")
        if not score_value:
            continue
        numeric = _score_to_numeric(str(score_value))
        if numeric is not None:
            best_score = numeric if best_score is None else max(best_score, numeric)

    if best_score is not None:
        return _severity_from_cvss_score(best_score)

    return "unknown"


def _extract_fixed_version(vuln: dict[str, Any], ecosystem: str) -> Optional[str]:
    for affected in vuln.get("affected", []) or []:
        pkg = affected.get("package") or {}
        if pkg.get("ecosystem") != ecosystem:
            continue
        for rng in affected.get("ranges", []) or []:
            for event in rng.get("events", []) or []:
                if "fixed" in event:
                    return event["fixed"]
    return None


def _summarize(vuln: dict[str, Any]) -> str:
    summary = vuln.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    details = vuln.get("details")
    if isinstance(details, str) and details.strip():
        first_line = details.strip().splitlines()[0]
        return first_line[:280]
    return "No summary available."


def _parse_vuln(vuln: dict[str, Any], ecosystem: str) -> VulnerabilityFinding:
    severity = resolve_severity(vuln)
    references = [
        ref.get("url") for ref in vuln.get("references", []) or [] if ref.get("url")
    ]
    return VulnerabilityFinding(
        id=vuln.get("id", "UNKNOWN"),
        summary=_summarize(vuln),
        severity=severity,
        fixed_version=_extract_fixed_version(vuln, ecosystem),
        references=references,
        points=_SEVERITY_POINTS[severity],
    )


async def check_vulnerabilities(
    client: httpx.AsyncClient,
    package_name: str,
    version: str,
    ecosystem: str = "npm",
) -> list[VulnerabilityFinding]:
    """Query OSV.dev for known vulnerabilities affecting this exact package
    version. Returns [] when the package is clean - never returns [] on a
    failed lookup, that case raises VulnCheckError instead so the caller
    can't confuse "checked, clean" with "didn't check"."""

    payload = {"package": {"name": package_name, "ecosystem": ecosystem}, "version": version}

    try:
        resp = await client.post(f"{OSV_API_BASE}/query", json=payload, timeout=_OSV_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise VulnCheckError(f"OSV.dev query failed: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise VulnCheckError(f"OSV.dev returned an unparseable response: {exc}") from exc

    vulns = data.get("vulns", []) or []
    return [_parse_vuln(v, ecosystem) for v in vulns]


async def check_vulnerabilities_batch(
    client: httpx.AsyncClient,
    packages: list[tuple[str, str, str]],
) -> dict[tuple[str, str], list[VulnerabilityFinding]]:
    """Bulk-check many (name, version, ecosystem) tuples in one request via
    POST /v1/querybatch (up to 1000 queries), then fetch full vulnerability
    records only for the IDs that actually hit via GET /v1/vulns/{id} -
    cheaper than one /v1/query call per package. Not wired into the
    single-package scan flow (see check_vulnerabilities above); this exists
    for Phase 9's repo-dependency scanning to reuse without a client rewrite.

    `packages` is a list of (name, version, ecosystem) tuples. Returns a dict
    keyed by (name, version) - each ecosystem/version combination should be
    unique per query, so the ecosystem itself isn't needed in the key.
    """
    if not packages:
        return {}

    queries = [
        {"package": {"name": name, "ecosystem": eco}, "version": version}
        for name, version, eco in packages
    ]

    try:
        resp = await client.post(
            f"{OSV_API_BASE}/querybatch", json={"queries": queries}, timeout=_OSV_TIMEOUT
        )
        resp.raise_for_status()
        batch_data = resp.json()
    except httpx.HTTPError as exc:
        raise VulnCheckError(f"OSV.dev batch query failed: {exc}") from exc
    except ValueError as exc:
        raise VulnCheckError(f"OSV.dev returned an unparseable batch response: {exc}") from exc

    results = batch_data.get("results", []) or []

    # Collect every vulnerability ID that hit, across all queries, deduped -
    # the same advisory commonly comes back for many packages/ecosystems.
    id_to_ecosystem: dict[str, str] = {}
    for (_name, _version, eco), result in zip(packages, results):
        for vuln_stub in result.get("vulns", []) or []:
            vuln_id = vuln_stub.get("id")
            if vuln_id:
                id_to_ecosystem.setdefault(vuln_id, eco)

    full_records: dict[str, dict[str, Any]] = {}
    for vuln_id in id_to_ecosystem:
        try:
            vuln_resp = await client.get(f"{OSV_API_BASE}/vulns/{vuln_id}", timeout=_OSV_TIMEOUT)
            vuln_resp.raise_for_status()
            full_records[vuln_id] = vuln_resp.json()
        except (httpx.HTTPError, ValueError):
            # One bad record shouldn't sink the whole batch; it's just
            # dropped from that query's result list.
            continue

    output: dict[tuple[str, str], list[VulnerabilityFinding]] = {}
    for (name, version, eco), result in zip(packages, results):
        findings = []
        for vuln_stub in result.get("vulns", []) or []:
            record = full_records.get(vuln_stub.get("id"))
            if record:
                findings.append(_parse_vuln(record, eco))
        output[(name, version)] = findings

    return output
