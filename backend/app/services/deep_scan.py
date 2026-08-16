"""Phase 4 placeholder: LLM-driven deep scan over a package's unpacked source.

Phase 1 has no tarball download/unpack step, so this module is not wired into
the pipeline yet. It exists now to pin the interface the deterministic scoring
layer (scoring.py) and the future LLM layer will share, and the trigger rule
that decides when a deep scan is warranted.

Future phase: download the package tarball, unpack it, and pass a mapping of
{file_path: file_contents} to run_deep_scan(), which will call an LLM to look
for things static heuristics miss (obfuscated payloads, exfiltration code,
suspicious network calls in install scripts, etc).
"""

from __future__ import annotations

from app.models.schemas import Finding

DEEP_SCAN_SCORE_THRESHOLD = 25


def should_trigger_deep_scan(risk_score: int, findings: list[Finding]) -> bool:
    """A deep scan is warranted when the deterministic layer already scored
    at or above the threshold, or raised any danger-severity finding."""
    if risk_score >= DEEP_SCAN_SCORE_THRESHOLD:
        return True
    return any(f.severity == "danger" for f in findings)


async def run_deep_scan(source_files: dict[str, str]) -> list[Finding]:
    """Analyze unpacked package source with an LLM and return findings.

    Args:
        source_files: mapping of relative file path -> file contents for the
            unpacked package tarball.

    Returns:
        A list of Finding objects (same shape as deterministic heuristics)
        contributed by the deep scan.

    Not implemented in Phase 1 — no LLM call is made yet.
    """
    raise NotImplementedError("Deep scan LLM layer is implemented in Phase 4")
