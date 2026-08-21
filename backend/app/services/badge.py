"""Shields.io-style SVG badge rendering and a short-lived scan cache for it.

Badges get embedded in READMEs and hit on every raw render, so this module
never triggers more than one live scan per package per _TTL_SECONDS - well
below that, it just replays the cached ScanResult (deep-scan LLM call and
all, per Phase 4's own caching).
"""

from __future__ import annotations

import time
from typing import Optional

from app.models.schemas import ScanResult, Verdict
from app.services import scanner
from app.services.npm_client import PackageNotFoundError

_TTL_SECONDS = 6 * 60 * 60  # 6 hours

_CACHE: dict[str, tuple[float, ScanResult]] = {}

_VERDICT_COLORS: dict[Verdict, str] = {
    "safe": "#22c55e",
    "suspicious": "#f59e0b",
    "investigate": "#ef4444",
}
_UNKNOWN_COLOR = "#9ca3af"


async def get_cached_scan(package_name: str) -> ScanResult:
    """Return a cached ScanResult if fresher than _TTL_SECONDS, else scan live."""
    now = time.monotonic()
    cached = _CACHE.get(package_name)
    if cached is not None and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    result = await scanner.scan_package("npm", package_name)
    _CACHE[package_name] = (now, result)
    return result


def verdict_color(verdict: Verdict) -> str:
    return _VERDICT_COLORS.get(verdict, _UNKNOWN_COLOR)


def _text_width(text: str) -> int:
    # Rough Verdana-11px average advance width; generous enough that text
    # never overflows its badge segment even though it isn't pixel-exact.
    return round(len(text) * 6.8) + 10


def render_badge(label: str, message: str, color: str) -> str:
    label_width = _text_width(label)
    value_width = _text_width(message)
    total_width = label_width + value_width
    label_x = label_width / 2
    value_x = label_width + value_width / 2

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {message}">
  <title>{label}: {message}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text x="{label_x}" y="14">{label}</text>
    <text x="{value_x}" y="14">{message}</text>
  </g>
</svg>
"""


async def build_badge_svg(package_name: str) -> str:
    try:
        result = await get_cached_scan(package_name)
    except PackageNotFoundError:
        return render_badge("PackageSafe", "not found", _UNKNOWN_COLOR)

    message = f"{result.risk_score}/100"
    return render_badge("PackageSafe", message, verdict_color(result.verdict))
