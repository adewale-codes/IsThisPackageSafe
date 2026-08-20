"""Phase 4: LLM-driven deep scan over a package's unpacked source.

Triggered by scanner.py when the deterministic heuristics layer (scoring.py)
already scored the package at or above DEEP_SCAN_SCORE_THRESHOLD, or raised a
danger-severity finding. The flow is:

    scanner.py
      -> deep_scan.should_trigger_deep_scan(risk_score, findings)
      -> deep_scan.perform_deep_scan(metadata, package_name)   # this module
           -> fetch_and_select_source()  download + unpack + candidate select
           -> run_deep_scan()            Claude API classification call
      -> fold finding.points into the final score

Cost/latency guards: results are cached in-process by tarball shasum (the
exact package version never needs a second LLM call), and the whole flow
(download + LLM) runs under one hard timeout so a slow/huge package can't
hang a scan indefinitely.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import re
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

import anthropic
import httpx
from pydantic import BaseModel

from app.models.schemas import DeepScanFinding, Finding, PackageMetadata

logger = logging.getLogger(__name__)

DEEP_SCAN_SCORE_THRESHOLD = 25

# Anthropic's "cheap/fast classification" tier - this is a bounded-output
# yes/no/summary classification over a handful of KB of source, not deep
# reasoning, so Haiku 4.5 is the right cost/latency tradeoff ($1/$5 per MTok
# vs. $3+/$15+ for Sonnet/Opus tiers). A scan sends at most ~50KB of source
# (~12-13K tokens) plus a short system prompt, and asks for a small JSON
# object back, so a single deep scan costs a fraction of a cent.
DEEP_SCAN_MODEL = "claude-haiku-4-5"

# Hard cap on the whole flow (tarball download + unpack + LLM call) so one
# slow or oversized package can't hang a scan.
DEEP_SCAN_HARD_TIMEOUT = 45.0
# Sub-budget for the LLM call itself.
_LLM_TIMEOUT = 25.0
# Sub-budget for the tarball download.
_DOWNLOAD_TIMEOUT = httpx.Timeout(15.0, read=20.0)

_MAX_SOURCE_BYTES = 50_000
_MAX_SINGLE_FILE_BYTES = 20_000
_SKIP_DIR_NAMES = {"node_modules", ".git", "test", "tests", "__tests__", "docs"}
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".node", ".wasm", ".map", ".lock",
    ".zip", ".gz", ".tar", ".7z",
}
_CANDIDATE_EXTENSIONS = {".js", ".cjs", ".mjs", ".ts", ".py", ".sh"}

_SUSPICIOUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\beval\s*\("), "uses eval()"),
    (re.compile(r"\bFunction\s*\(\s*['\"]"), "constructs code via Function()"),
    (re.compile(r"\bchild_process\b"), "spawns processes via child_process"),
    (re.compile(r"require\(\s*['\"]https?['\"]\s*\)"), "requires http/https directly"),
    (re.compile(r"\bBuffer\.from\([^)]*['\"]base64['\"]"), "decodes base64 payloads"),
    (re.compile(r"process\.env\b"), "reads process.env"),
]

_SCRIPT_PATH_RE = re.compile(r"[.\w/-]+\.(?:js|cjs|mjs|ts|py|sh)\b")


class IntegrityError(Exception):
    """Raised when a downloaded tarball's shasum doesn't match the registry's."""


# In-process cache keyed by tarball shasum. A given package version's
# tarball never changes, so once we've deep-scanned a shasum there's no
# reason to pay for another LLM call - this is the single biggest cost
# control available given neither Phase 1 nor Phase 2 have a cache yet.
_RESULT_CACHE: dict[str, DeepScanFinding] = {}


def should_trigger_deep_scan(risk_score: int, findings: list[Finding]) -> bool:
    """A deep scan is warranted when the deterministic layer already scored
    at or above the threshold, or raised any danger-severity finding."""
    if risk_score >= DEEP_SCAN_SCORE_THRESHOLD:
        return True
    return any(f.severity == "danger" for f in findings)


def _is_safe_member(member: tarfile.TarInfo, dest: Path) -> bool:
    target = (dest / member.name).resolve()
    try:
        target.relative_to(dest.resolve())
    except ValueError:
        return False
    return member.isfile() or member.isdir()


def _extract_tarball(tarball_bytes: bytes, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tar:
        safe_members = [m for m in tar.getmembers() if _is_safe_member(m, dest)]
        try:
            tar.extractall(dest, members=safe_members, filter="data")
        except TypeError:
            # Python < 3.11.4 without PEP 706 filter support.
            tar.extractall(dest, members=safe_members)


def _package_root(dest: Path) -> Path:
    # npm tarballs conventionally unpack into a single top-level "package/" dir.
    candidate = dest / "package"
    return candidate if candidate.is_dir() else dest


def _iter_source_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in _SKIP_EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size == 0 or size > 500_000:
            continue
        yield path


def _read_text(path: Path, limit: int = _MAX_SINGLE_FILE_BYTES) -> Optional[str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    text = raw.decode("utf-8", errors="replace")
    if len(text) > limit:
        text = text[:limit] + "\n... [truncated]"
    return text


def _extract_script_paths(install_scripts: dict[str, str]) -> list[str]:
    paths: list[str] = []
    for command in install_scripts.values():
        for match in _SCRIPT_PATH_RE.findall(command):
            if match not in paths:
                paths.append(match)
    return paths


def _read_entry_point(root: Path) -> Optional[str]:
    package_json = root / "package.json"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None

    main = data.get("main")
    if isinstance(main, str):
        return main

    exports = data.get("exports")
    if isinstance(exports, str):
        return exports
    if isinstance(exports, dict):
        default = exports.get(".") or exports.get("default")
        if isinstance(default, str):
            return default
        if isinstance(default, dict):
            for key in ("require", "import", "default"):
                if isinstance(default.get(key), str):
                    return default[key]
    return None


def _suspicion_reasons(content: str) -> list[str]:
    reasons: list[str] = []

    total_chars = len(content)
    if total_chars > 500:
        ws_ratio = sum(1 for c in content if c.isspace()) / total_chars
        if ws_ratio < 0.05:
            reasons.append("very low whitespace-to-character ratio (possibly minified)")

    longest_line = max((len(line) for line in content.splitlines()), default=0)
    if longest_line > 500:
        reasons.append(f"contains a very long single line ({longest_line} chars)")

    for pattern, label in _SUSPICIOUS_PATTERNS:
        if pattern.search(content):
            reasons.append(label)

    return reasons


def _select_candidates(root: Path, metadata: PackageMetadata) -> list[tuple[str, str, list[str]]]:
    """Return (relative_path, content, reasons) tuples, install-script-linked
    and entry-point files first, then pattern-flagged files, most-suspicious
    first - the priority order candidates are added to the LLM prompt in."""

    script_paths = set(_extract_script_paths(metadata.install_scripts))
    entry_point = _read_entry_point(root)

    tier0: list[tuple[str, str, list[str]]] = []  # install-script-linked
    tier1: list[tuple[str, str, list[str]]] = []  # main entry point
    tier2: list[tuple[str, int, str, list[str]]] = []  # suspicious-pattern-flagged

    seen: set[str] = set()

    for path in _iter_source_files(root):
        rel = str(path.relative_to(root))
        if rel in seen:
            continue

        is_script_hit = any(rel == s or rel.endswith("/" + s) for s in script_paths)
        is_entry = entry_point is not None and (
            rel == entry_point or rel == entry_point.lstrip("./")
        )

        if not (is_script_hit or is_entry) and path.suffix.lower() not in _CANDIDATE_EXTENSIONS:
            continue

        content = _read_text(path)
        if content is None:
            continue

        if is_script_hit:
            seen.add(rel)
            tier0.append((rel, content, ["referenced by an install lifecycle script"]))
        elif is_entry:
            seen.add(rel)
            tier1.append((rel, content, ["package entry point (main/exports)"]))
        else:
            reasons = _suspicion_reasons(content)
            if reasons:
                seen.add(rel)
                tier2.append((rel, len(reasons), content, reasons))

    tier2.sort(key=lambda item: item[1], reverse=True)
    tier2_sorted = [(rel, content, reasons) for rel, _score, content, reasons in tier2]

    return tier0 + tier1 + tier2_sorted


def _cap_to_budget(
    candidates: list[tuple[str, str, list[str]]], max_bytes: int = _MAX_SOURCE_BYTES
) -> dict[str, str]:
    selected: dict[str, str] = {}
    used = 0
    for rel, content, reasons in candidates:
        header = f"# reasons: {', '.join(reasons)}\n"
        entry = header + content
        remaining = max_bytes - used
        if remaining <= 0:
            break
        if len(entry) > remaining:
            entry = entry[:remaining] + "\n... [truncated to fit scan budget]"
        selected[rel] = entry
        used += len(entry)
        if used >= max_bytes:
            break
    return selected


async def fetch_and_select_source(
    metadata: PackageMetadata, *, http_client: Optional[httpx.AsyncClient] = None
) -> dict[str, str]:
    """Download the package tarball, verify its shasum, unpack it to a temp
    directory, select a small high-signal subset of files, and return
    {relative_path: content}. The temp directory is always cleaned up, even
    on error, via the TemporaryDirectory context manager."""

    if not metadata.tarball_url:
        return {}

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True)

    try:
        resp = await client.get(metadata.tarball_url)
        resp.raise_for_status()
        tarball_bytes = resp.content
    finally:
        if owns_client:
            await client.aclose()

    if metadata.tarball_shasum:
        actual = hashlib.sha1(tarball_bytes).hexdigest()
        if actual != metadata.tarball_shasum:
            raise IntegrityError(
                f"Tarball shasum mismatch for {metadata.name}: "
                f"expected {metadata.tarball_shasum}, got {actual}"
            )

    with tempfile.TemporaryDirectory(prefix="packagesafe-deepscan-") as tmp:
        dest = Path(tmp)
        _extract_tarball(tarball_bytes, dest)
        root = _package_root(dest)
        candidates = _select_candidates(root, metadata)
        return _cap_to_budget(candidates)


_SYSTEM_PROMPT = """\
You are a security analyst reviewing npm package source code for supply-chain \
risk. You will be given a package's name, its stated description, and a small \
set of high-signal source file excerpts (install scripts, the entry point, and \
files flagged as possibly obfuscated).

Assess specifically:
1. Code obfuscation - minification, encoded/packed payloads, unusual control \
   flow that hides what the code does.
2. Unexplained network calls - requests to hosts that have no obvious relation \
   to the package's stated purpose.
3. Data exfiltration patterns - code that reads sensitive data (environment \
   variables, credentials, SSH keys, browser data) and sends it somewhere.
4. Whether the code's actual behavior plausibly matches what a package with \
   this name and description would do.

Respond with ONLY a JSON object matching exactly this shape, no other text:
{
  "obfuscation_detected": boolean,
  "suspicious_network_calls": boolean,
  "matches_stated_purpose": boolean,
  "summary": "one or two sentences, human-readable, explaining what you found",
  "severity_points": integer from 0 to 40, how many risk points this warrants
}

Points guidance: 0 if nothing concerning; 5-15 for minor concerns (unexplained \
but likely benign network calls, mild obfuscation); 20-30 for clear obfuscation \
or exfiltration-shaped code; 35-40 for code that is almost certainly malicious.
"""


class _Classification(BaseModel):
    obfuscation_detected: bool
    suspicious_network_calls: bool
    matches_stated_purpose: bool
    summary: str
    severity_points: int


def _build_user_prompt(package_name: str, description: Optional[str], source_files: dict[str, str]) -> str:
    parts = [
        f"Package: {package_name}",
        f"Stated description: {description or '(none provided)'}",
        "",
        "Source excerpts:",
    ]
    for path, content in source_files.items():
        parts.append(f"\n--- {path} ---\n{content}")
    return "\n".join(parts)


async def run_deep_scan(
    package_name: str,
    source_files: dict[str, str],
    *,
    description: Optional[str] = None,
    tarball_shasum: Optional[str] = None,
) -> DeepScanFinding:
    """Classify a package's selected source with the Claude API.

    Returns a DeepScanFinding describing the outcome. On any error or
    timeout this returns status="failed" with an explanatory summary rather
    than silently reporting a clean result - a failed deep scan must never
    be presented as a false-negative "safe".
    """

    if not source_files:
        return DeepScanFinding(
            status="skipped",
            summary="No candidate source files were available to analyze (no tarball, "
            "or nothing matched the selection heuristics).",
            points=0,
        )

    if tarball_shasum and tarball_shasum in _RESULT_CACHE:
        cached = _RESULT_CACHE[tarball_shasum]
        return cached.model_copy(update={"cached": True})

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.with_options(timeout=_LLM_TIMEOUT).messages.parse(
            model=DEEP_SCAN_MODEL,
            max_tokens=1024,
            temperature=0,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_user_prompt(package_name, description, source_files),
                }
            ],
            output_format=_Classification,
        )
    except anthropic.APIError as exc:
        logger.warning("Deep scan LLM call failed for %s: %s", package_name, exc)
        return DeepScanFinding(
            status="failed",
            summary=f"Deep scan did not complete: the Claude API call failed ({exc}).",
            points=0,
        )
    except Exception as exc:  # noqa: BLE001 - genuinely any failure must not look like "safe"
        logger.warning("Deep scan failed unexpectedly for %s: %s", package_name, exc)
        return DeepScanFinding(
            status="failed",
            summary=f"Deep scan did not complete due to an unexpected error ({exc}).",
            points=0,
        )

    parsed = response.parsed_output
    if parsed is None:
        return DeepScanFinding(
            status="failed",
            summary="Deep scan did not complete: the model's response could not be parsed "
            "into the expected JSON shape.",
            points=0,
        )

    points = max(0, min(40, parsed.severity_points))
    summary = parsed.summary
    if not parsed.matches_stated_purpose:
        summary += " Behavior does not clearly match the package's stated purpose."

    finding = DeepScanFinding(
        status="completed",
        obfuscation_detected=parsed.obfuscation_detected,
        suspicious_network_calls=parsed.suspicious_network_calls,
        summary=summary,
        points=points,
        cached=False,
    )

    if tarball_shasum:
        _RESULT_CACHE[tarball_shasum] = finding

    return finding


async def perform_deep_scan(
    metadata: PackageMetadata,
    package_name: str,
    *,
    http_client: Optional[httpx.AsyncClient] = None,
) -> DeepScanFinding:
    """Entry point scanner.py calls: fetch+unpack+select, then classify, all
    under one hard timeout covering the whole flow."""

    async def _flow() -> DeepScanFinding:
        try:
            source_files = await fetch_and_select_source(metadata, http_client=http_client)
        except IntegrityError as exc:
            logger.warning("Deep scan integrity check failed for %s: %s", package_name, exc)
            return DeepScanFinding(
                status="failed",
                summary=f"Deep scan did not complete: tarball integrity check failed ({exc}).",
                points=0,
            )
        except httpx.HTTPError as exc:
            logger.warning("Deep scan tarball download failed for %s: %s", package_name, exc)
            return DeepScanFinding(
                status="failed",
                summary=f"Deep scan did not complete: could not download the package tarball ({exc}).",
                points=0,
            )
        except (tarfile.TarError, OSError) as exc:
            logger.warning("Deep scan tarball unpack failed for %s: %s", package_name, exc)
            return DeepScanFinding(
                status="failed",
                summary=f"Deep scan did not complete: could not unpack the package tarball ({exc}).",
                points=0,
            )

        return await run_deep_scan(
            package_name,
            source_files,
            description=metadata.description,
            tarball_shasum=metadata.tarball_shasum,
        )

    try:
        return await asyncio.wait_for(_flow(), timeout=DEEP_SCAN_HARD_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("Deep scan timed out for %s", package_name)
        return DeepScanFinding(
            status="failed",
            summary=f"Deep scan did not complete within {DEEP_SCAN_HARD_TIMEOUT:.0f}s and was aborted.",
            points=0,
        )
