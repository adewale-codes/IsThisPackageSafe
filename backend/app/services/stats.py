"""Phase 12: aggregate, privacy-preserving usage stats for the public
/stats endpoint and /transparency page.

Recording is intentionally coarse and best-effort:

- One `record_scan()` call per *completed* scan (single-package, tree, or
  repo), built from every package actually scanned in it - not per HTTP
  request, and never per intermediate step.
- A recording failure (DB down, pool not initialized) is logged and
  swallowed, never raised - a stats-recording problem must not turn into a
  scan-request failure. See db.py for why "no DATABASE_URL" makes every
  function here a no-op (that's also the deliberately simple way test/dev
  environments don't pollute the public numbers).
- What's stored is a running SUM per (day, metric) - not a log of events,
  not a list of packages, not anything with a timestamp finer than a day.
  seen_packages stores bare (ecosystem, name) identity with nothing else,
  solely so "unique packages scanned" can be a real distinct count rather
  than a guess - see db.py's schema comment for why that's not the same
  thing as the search-history tracking this phase explicitly avoids.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal, Optional

from app.models.schemas import ScanResult
from app.services import db

logger = logging.getLogger(__name__)

ScanType = Literal["single", "tree", "repo"]

_CACHE_TTL_SECONDS = 5 * 60
_cache: Optional[tuple[float, dict]] = None


@dataclass
class ScanEventBatch:
    scan_type: ScanType
    ecosystem_counts: dict[str, int] = field(default_factory=dict)
    vuln_severity_counts: dict[str, int] = field(default_factory=dict)
    heuristic_finding_count: int = 0
    unique_packages: set[tuple[str, str]] = field(default_factory=set)


def batch_from_results(scan_type: ScanType, results: list[ScanResult]) -> ScanEventBatch:
    """Builds one batch from every package actually scanned in a completed
    scan - for "single" that's one ScanResult; for "tree"/"repo" it's the
    root plus every transitive/direct dependency that got a real scan
    (including clean ones, so ecosystem/unique-package counts aren't
    skewed toward only-the-flagged-ones)."""
    batch = ScanEventBatch(scan_type=scan_type)
    for r in results:
        batch.ecosystem_counts[r.ecosystem] = batch.ecosystem_counts.get(r.ecosystem, 0) + 1
        batch.heuristic_finding_count += len(r.findings)
        for v in r.vulnerabilities:
            batch.vuln_severity_counts[v.severity] = batch.vuln_severity_counts.get(v.severity, 0) + 1
        batch.unique_packages.add((r.ecosystem, r.package.lower()))
    return batch


async def record_scan(batch: ScanEventBatch) -> None:
    pool = db.get_pool()
    if pool is None:
        return

    today = date.today()

    increments: dict[str, int] = {f"scans_{batch.scan_type}": 1}
    for eco, count in batch.ecosystem_counts.items():
        key = f"ecosystem_{eco}"
        increments[key] = increments.get(key, 0) + count
    for sev, count in batch.vuln_severity_counts.items():
        key = f"vuln_{sev}"
        increments[key] = increments.get(key, 0) + count
    if batch.heuristic_finding_count:
        increments["heuristic_findings"] = increments.get("heuristic_findings", 0) + batch.heuristic_finding_count

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for metric, delta in increments.items():
                    await conn.execute(
                        """
                        INSERT INTO daily_stats (day, metric, count)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (day, metric) DO UPDATE SET count = daily_stats.count + EXCLUDED.count
                        """,
                        today,
                        metric,
                        delta,
                    )
                if batch.unique_packages:
                    await conn.executemany(
                        "INSERT INTO seen_packages (ecosystem, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                        list(batch.unique_packages),
                    )
    except Exception as exc:  # noqa: BLE001 - recording must never fail the scan it's attached to
        logger.warning("Failed to record scan stats (non-fatal): %s", exc)


_ECOSYSTEMS = ("npm", "pypi", "maven")
_SEVERITIES = ("critical", "high", "medium", "low", "unknown")


async def _query_aggregated_stats() -> dict:
    pool = db.get_pool()
    if pool is None:
        return {
            "recording_enabled": False,
            "tracking_since": None,
            "scans": {"single": 0, "tree": 0, "repo": 0, "total": 0},
            "unique_packages_scanned": 0,
            "ecosystems": {eco: 0 for eco in _ECOSYSTEMS},
            "vulnerabilities_found": {**{s: 0 for s in _SEVERITIES}, "total": 0},
            "heuristic_findings_triggered": 0,
        }

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT metric, SUM(count) AS total FROM daily_stats GROUP BY metric")
        earliest = await conn.fetchval("SELECT MIN(day) FROM daily_stats")
        unique_count = await conn.fetchval("SELECT COUNT(*) FROM seen_packages")

    totals = {row["metric"]: int(row["total"]) for row in rows}

    scans = {
        "single": totals.get("scans_single", 0),
        "tree": totals.get("scans_tree", 0),
        "repo": totals.get("scans_repo", 0),
    }
    scans["total"] = sum(scans.values())

    ecosystems = {eco: totals.get(f"ecosystem_{eco}", 0) for eco in _ECOSYSTEMS}

    vulnerabilities = {sev: totals.get(f"vuln_{sev}", 0) for sev in _SEVERITIES}
    vulnerabilities["total"] = sum(vulnerabilities.values())

    return {
        "recording_enabled": True,
        "tracking_since": earliest.isoformat() if earliest else None,
        "scans": scans,
        "unique_packages_scanned": unique_count or 0,
        "ecosystems": ecosystems,
        "vulnerabilities_found": vulnerabilities,
        "heuristic_findings_triggered": totals.get("heuristic_findings", 0),
    }


async def get_cached_stats() -> dict:
    """5-minute TTL in-process cache - GET /stats is public and could be
    hit often; recomputing two aggregate queries on every request isn't
    worth it for numbers that only need daily-ish freshness."""
    global _cache
    now = time.monotonic()
    if _cache is not None and (now - _cache[0]) < _CACHE_TTL_SECONDS:
        return _cache[1]

    result = await _query_aggregated_stats()
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    _cache = (now, result)
    return result
