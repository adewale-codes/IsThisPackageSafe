"""Deterministic heuristic rules and scoring/verdict logic.

Each rule function inspects one slice of the gathered data and returns zero or
more Finding objects. This module is intentionally swappable: scanner.py only
depends on run_heuristics(), compute_score(), and compute_verdict(), so the
rule set can be extended or replaced without touching the orchestration layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.models.schemas import DownloadStats, Finding, GithubSignals, PackageMetadata, Verdict
from app.services import npm_client, typosquat

MAX_SCORE = 100
INVESTIGATE_THRESHOLD = 60
SUSPICIOUS_THRESHOLD = 25

_DEP_COUNT_WARNING = 40
_DEP_COUNT_INFO = 20

_POPULARITY_DOWNLOAD_THRESHOLD = 10_000
_POPULARITY_STAR_THRESHOLD = 50


def _now() -> datetime:
    return datetime.now(timezone.utc)


def rule_package_age(metadata: PackageMetadata) -> Optional[Finding]:
    if metadata.first_published_at is None:
        return None

    age_days = (_now() - metadata.first_published_at).days

    if age_days < 7:
        return Finding(
            id="package_age",
            label="Very new package",
            severity="danger",
            points=30,
            detail=f"Package was first published {age_days} day(s) ago (under 7 days).",
        )
    if age_days < 30:
        return Finding(
            id="package_age",
            label="Recently published package",
            severity="warning",
            points=15,
            detail=f"Package was first published {age_days} day(s) ago (under 30 days).",
        )
    return None


def rule_maintainer_change(packument: dict[str, Any], metadata: PackageMetadata) -> Optional[Finding]:
    history = npm_client.get_ordered_version_history(packument)
    if len(history) < 2:
        return None

    versions = [v for v, _ in history]
    latest_transition_index = len(versions) - 2

    for i in range(len(versions) - 1):
        prev_version, curr_version = versions[i], versions[i + 1]
        prev_maintainers = set(npm_client.get_maintainers_for_version(packument, prev_version))
        curr_maintainers = set(npm_client.get_maintainers_for_version(packument, curr_version))

        if not prev_maintainers or not curr_maintainers:
            continue

        if prev_maintainers.isdisjoint(curr_maintainers):
            is_latest = i == latest_transition_index
            if is_latest:
                return Finding(
                    id="maintainer_takeover",
                    label="Full maintainer replacement in latest version",
                    severity="danger",
                    points=35,
                    detail=(
                        f"All maintainers changed between {prev_version} ({', '.join(sorted(prev_maintainers))}) "
                        f"and {curr_version} ({', '.join(sorted(curr_maintainers))}) - a classic package "
                        "takeover signal."
                    ),
                )
            return Finding(
                id="maintainer_change_history",
                label="Full maintainer replacement in package history",
                severity="warning",
                points=15,
                detail=(
                    f"All maintainers changed between {prev_version} and {curr_version} earlier in the "
                    "package's history."
                ),
            )

    return None


def rule_install_scripts(metadata: PackageMetadata) -> Optional[Finding]:
    if not metadata.install_scripts:
        return None

    script_names = ", ".join(sorted(metadata.install_scripts.keys()))
    points = min(10 + 5 * (len(metadata.install_scripts) - 1), 20)

    return Finding(
        id="install_scripts",
        label="Runs code automatically on install",
        severity="warning",
        points=points,
        detail=f"Package defines lifecycle script(s) that execute on install: {script_names}.",
    )


def rule_typosquat(package_name: str) -> Optional[Finding]:
    match = typosquat.closest_popular_match(package_name)
    if match is None:
        return None

    popular_name, distance = match
    severity = "danger" if distance <= 1 else "warning"
    points = 30 if distance <= 1 else 20

    return Finding(
        id="typosquat",
        label="Possible typosquat of a popular package",
        severity=severity,
        points=points,
        detail=(
            f"Name '{package_name}' is within edit distance {distance} of popular package "
            f"'{popular_name}' but does not match it exactly."
        ),
    )


def rule_dependency_count(metadata: PackageMetadata) -> Optional[Finding]:
    count = metadata.dependency_count
    if count > _DEP_COUNT_WARNING:
        return Finding(
            id="dependency_count",
            label="Unusually high dependency count",
            severity="warning",
            points=15,
            detail=f"Package declares {count} direct dependencies, increasing supply-chain attack surface.",
        )
    if count > _DEP_COUNT_INFO:
        return Finding(
            id="dependency_count",
            label="High dependency count",
            severity="info",
            points=5,
            detail=f"Package declares {count} direct dependencies.",
        )
    return None


def rule_repo_npm_mismatch(metadata: PackageMetadata, github: GithubSignals) -> list[Finding]:
    findings: list[Finding] = []

    if not metadata.repository.owner or not metadata.repository.repo:
        findings.append(
            Finding(
                id="no_repository",
                label="No linked source repository",
                severity="info",
                points=5,
                detail="Package metadata does not link to a GitHub repository.",
            )
        )
        return findings

    if github.exists is False:
        findings.append(
            Finding(
                id="repository_missing",
                label="Linked repository does not exist",
                severity="warning",
                points=15,
                detail=(
                    f"Package links to {metadata.repository.owner}/{metadata.repository.repo} on GitHub, "
                    "but that repository could not be found."
                ),
            )
        )
        return findings

    if github.archived:
        findings.append(
            Finding(
                id="repository_archived",
                label="Linked repository is archived",
                severity="warning",
                points=15,
                detail=f"GitHub repository {github.owner}/{github.repo} is archived (read-only).",
            )
        )

    if (
        metadata.latest_published_at is not None
        and github.last_pushed_at is not None
    ):
        latest_published = metadata.latest_published_at
        last_pushed = github.last_pushed_at
        days_since_npm_publish = (_now() - latest_published).days
        gap_days = (latest_published - last_pushed).days

        if days_since_npm_publish < 30 and gap_days > 90:
            findings.append(
                Finding(
                    id="repo_npm_activity_mismatch",
                    label="npm release not reflected in repository activity",
                    severity="warning",
                    points=15,
                    detail=(
                        f"Latest npm version was published {days_since_npm_publish} day(s) ago, but the "
                        f"linked repository's last commit was {gap_days} day(s) before that publish."
                    ),
                )
            )

    return findings


def rule_popularity_anomaly(downloads: DownloadStats, github: GithubSignals) -> Optional[Finding]:
    if not downloads.available or downloads.downloads < _POPULARITY_DOWNLOAD_THRESHOLD:
        return None

    if not github.linked or github.exists is not True:
        return None

    low_stars = (github.stars or 0) < _POPULARITY_STAR_THRESHOLD
    low_contributors = (github.contributors_count or 0) <= 1

    if low_stars or low_contributors:
        return Finding(
            id="popularity_anomaly",
            label="High downloads with minimal GitHub footprint",
            severity="warning",
            points=15,
            detail=(
                f"{downloads.downloads:,} downloads in {downloads.period} vs. "
                f"{github.stars or 0} stars and {github.contributors_count or 'unknown'} contributor(s) "
                "on the linked repository."
            ),
        )
    return None


def run_heuristics(
    package_name: str,
    packument: dict[str, Any],
    metadata: PackageMetadata,
    downloads: DownloadStats,
    github: GithubSignals,
) -> list[Finding]:
    findings: list[Finding] = []

    for finding in (
        rule_package_age(metadata),
        rule_maintainer_change(packument, metadata),
        rule_install_scripts(metadata),
        rule_typosquat(package_name),
        rule_dependency_count(metadata),
        rule_popularity_anomaly(downloads, github),
    ):
        if finding is not None:
            findings.append(finding)

    findings.extend(rule_repo_npm_mismatch(metadata, github))

    return findings


def compute_score(findings: list[Finding]) -> int:
    return min(sum(f.points for f in findings), MAX_SCORE)


def compute_verdict(score: int) -> Verdict:
    if score >= INVESTIGATE_THRESHOLD:
        return "investigate"
    if score >= SUSPICIOUS_THRESHOLD:
        return "suspicious"
    return "safe"
