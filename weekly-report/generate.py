"""Weekly content job: bulk-scans a curated list of popular npm packages,
ranks them by PackageSafe risk score, and publishes a "riskiest packages
this week" report - the recurring distribution mechanism referenced in the
Phase 5 plan.

Cron-runnable via `.github/workflows/weekly-report.yml` (schedule +
workflow_dispatch), or any plain cron pointed at this script wherever the
backend is deployed.

Output:
  web/content/reports/<YYYY-MM-DD>.json  (dated snapshot)
  web/content/reports/latest.json        (what the /reports page reads)
  web/content/reports/<YYYY-MM-DD>-share.txt  (X/LinkedIn copy)

No new scoring logic here - this is purely a client of the existing
Phase 1 API's GET /scan/{package}, same pattern as the CLI and web app.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "web" / "content" / "reports"

DEFAULT_API_URL = "http://localhost:8000"

# A curated slice of well-established, genuinely popular npm packages -
# not a "trending" API (none was specified in the brief), but a fixed seed
# list broad enough that real heuristic variance (archived repos, high
# dependency counts, deprecated/unmaintained packages) shows up on its own.
SEED_PACKAGES = [
    "react",
    "vue",
    "express",
    "lodash",
    "axios",
    "webpack",
    "@babel/core",
    "typescript",
    "eslint",
    "jest",
    "chalk",
    "commander",
    "moment",
    "request",
    "async",
    "jquery",
    "next",
    "redux",
    "rxjs",
    "socket.io",
    "prettier",
    "dotenv",
    "node-sass",
    "colors",
    "faker",
    "event-stream",
    "left-pad",
]


def resolve_api_url() -> str:
    return os.environ.get("PACKAGESAFE_API_URL", DEFAULT_API_URL).rstrip("/")


def build_scan_url(api_url: str, package_name: str) -> str:
    # Match the CLI/web client's encoding: percent-encode each path segment.
    encoded = "/".join(quote(part, safe="") for part in package_name.split("/"))
    return f"{api_url}/scan/{encoded}"


def scan_package(client: httpx.Client, api_url: str, package_name: str) -> dict:
    url = build_scan_url(api_url, package_name)
    resp = client.get(url, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def run_scans(api_url: str, packages: list[str]) -> tuple[list[dict], list[dict]]:
    scanned: list[dict] = []
    failed: list[dict] = []

    with httpx.Client() as client:
        for name in packages:
            print(f"Scanning {name}...", file=sys.stderr)
            try:
                result = scan_package(client, api_url, name)
                scanned.append(result)
            except httpx.HTTPError as exc:
                print(f"  failed: {exc}", file=sys.stderr)
                failed.append({"package": name, "error": str(exc)})

    return scanned, failed


def build_report(scanned: list[dict], failed: list[dict]) -> dict:
    ranked = sorted(scanned, key=lambda r: r["risk_score"], reverse=True)
    entries = [
        {
            "rank": i + 1,
            "package": r["package"],
            "version": r["resolved_version"],
            "risk_score": r["risk_score"],
            # Additive - the API includes this alongside risk_score now (see
            # backend's ScanResult.safety_score); .get() so this script
            # doesn't break if pointed at an older backend that predates it.
            "safety_score": r.get("safety_score", 100 - r["risk_score"]),
            "verdict": r["verdict"],
            "description": r["metadata"].get("description"),
            "top_finding": (
                max(
                    (f for f in r["findings"] if f["points"] > 0),
                    key=lambda f: f["points"],
                    default=None,
                )
            ),
        }
        for i, r in enumerate(ranked)
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_label": f"Week of {date.today().isoformat()}",
        "packages_scanned": len(scanned),
        "packages_failed": len(failed),
        "failed": failed,
        "packages": entries,
    }


def build_share_copy(report: dict) -> str:
    top3 = report["packages"][:3]
    if not top3:
        return "PackageSafe scanned this week's tracked packages - nothing flagged. 🟢"

    lines = [
        f"📊 PackageSafe's riskiest npm packages this week ({report['period_label']}):",
        "",
    ]
    for entry in top3:
        icon = {"safe": "🟢", "suspicious": "🟡", "investigate": "🔴"}.get(entry["verdict"], "⚪")
        finding_note = f" - {entry['top_finding']['label']}" if entry["top_finding"] else ""
        lines.append(f"{icon} {entry['package']}: {entry['risk_score']}/100{finding_note}")

    lines += [
        "",
        "Full ranking + why each package scored what it did: https://packagesafe.dev/reports",
        "",
        "#npm #supplychainsecurity #opensource",
    ]
    return "\n".join(lines)


def main() -> None:
    # Windows consoles often default stdout to cp1252, which can't encode
    # the emoji used in the summary output below.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    api_url = resolve_api_url()
    print(f"PackageSafe weekly report - scanning {len(SEED_PACKAGES)} packages against {api_url}")

    scanned, failed = run_scans(api_url, SEED_PACKAGES)
    if not scanned:
        print("No packages scanned successfully; aborting without writing a report.", file=sys.stderr)
        sys.exit(1)

    report = build_report(scanned, failed)
    share_copy = build_share_copy(report)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today_str = date.today().isoformat()
    dated_path = OUTPUT_DIR / f"{today_str}.json"
    latest_path = OUTPUT_DIR / "latest.json"
    share_path = OUTPUT_DIR / f"{today_str}-share.txt"

    dated_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    share_path.write_text(share_copy, encoding="utf-8")

    print(f"\nWrote {dated_path}")
    print(f"Wrote {latest_path}")
    print(f"Wrote {share_path}")

    print("\n=== Top 10 riskiest ===")
    for entry in report["packages"][:10]:
        icon = {"safe": "🟢", "suspicious": "🟡", "investigate": "🔴"}.get(entry["verdict"], "⚪")
        print(f"{entry['rank']:>2}. {icon} {entry['package']:<20} {entry['risk_score']:>3}/100  {entry['verdict']}")

    print("\n=== Share copy ===")
    print(share_copy)


if __name__ == "__main__":
    main()
