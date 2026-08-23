"""Phase 9: resolves a manifest's version constraint to a concrete version
that exists in the registry, by picking the highest version in a candidate
list (from EcosystemClient.fetch_versions()) that satisfies the constraint.

Three different constraint grammars, one per ecosystem:
- npm: semver ranges (^1.2.3, ~1.2.3, >=1.0.0 <2.0.0, 1.x, ||, hyphen
  ranges). Hand-rolled below - pragmatic coverage of what real package.json
  files actually use, not a full semver-spec-compliant implementation
  (notably: prerelease versions are excluded from "latest satisfying"
  unless nothing else matches, matching normal user expectations of "give
  me the latest *stable* version that fits").
- PyPI: PEP 440 specifiers (>=2.0,<3.0, ~=1.4, ==1.2.3, ...) via the
  `packaging` library - a real spec, not worth re-implementing.
- Maven: version ranges are rare in practice (most POMs pin an exact
  version, or omit one entirely to inherit from a parent/BOM this project
  doesn't resolve - see ecosystems/maven.py). manifest.py already resolves
  simple ${property} substitution; anything left unconstrained here just
  falls through to "no constraint -> latest", which is the same graceful
  simplification Phase 8 already makes for transitive Maven dependencies.
"""

from __future__ import annotations

import re
from typing import Optional

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

# ---------------------------------------------------------------------------
# npm / semver
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)

SemverTuple = tuple[int, int, int, tuple[str, ...]]


def parse_semver(version: str) -> Optional[SemverTuple]:
    match = _SEMVER_RE.match(version.strip())
    if not match:
        return None
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    return major, minor, patch, prerelease


def _prerelease_key(parts: tuple[str, ...]) -> tuple:
    # Numeric identifiers sort numerically and before alphanumeric ones, per
    # semver precedence rules; an empty tuple (no prerelease) sorts highest.
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts)


def compare_semver(a: SemverTuple, b: SemverTuple) -> int:
    a_core, b_core = a[:3], b[:3]
    if a_core != b_core:
        return -1 if a_core < b_core else 1
    a_pre, b_pre = a[3], b[3]
    if not a_pre and not b_pre:
        return 0
    if not a_pre:
        return 1  # no prerelease > has prerelease
    if not b_pre:
        return -1
    a_key, b_key = _prerelease_key(a_pre), _prerelease_key(b_pre)
    return -1 if a_key < b_key else (1 if a_key > b_key else 0)


def _partial_to_bounds(spec: str) -> Optional[tuple[SemverTuple, SemverTuple]]:
    """"1.2.x"/"1.2"/"1"/"*"/"" -> [floor, ceiling) as full (major,minor,patch)
    tuples, matching npm's x-range semantics (missing/x components float).
    The bound depends on how many leading numeric components were actually
    given (1 -> major-only range, 2 -> minor range, 3 -> exact), not on how
    many dot-separated parts the string has (so "1.2.x" - 2 numeric parts
    before the wildcard - correctly yields a minor-level range, not a
    major-level one)."""
    spec = spec.strip()
    if spec in ("", "*", "x", "X"):
        return (0, 0, 0, ()), (10**9, 0, 0, ())
    nums: list[int] = []
    for part in spec.split("."):
        if part in ("x", "X", "*"):
            break
        if not part.isdigit():
            return None
        nums.append(int(part))
        if len(nums) == 3:
            break

    if len(nums) == 0:
        return None
    if len(nums) == 1:
        return (nums[0], 0, 0, ()), (nums[0] + 1, 0, 0, ())
    if len(nums) == 2:
        return (nums[0], nums[1], 0, ()), (nums[0], nums[1] + 1, 0, ())
    # All three numeric components given but didn't parse via parse_semver
    # (e.g. malformed trailing text) - treat as an exact-match range.
    floor = (nums[0], nums[1], nums[2], ())
    return floor, floor


def _caret_bounds(base: SemverTuple) -> tuple[SemverTuple, SemverTuple]:
    major, minor, patch, _ = base
    if major > 0:
        return base, (major + 1, 0, 0, ())
    if minor > 0:
        return base, (0, minor + 1, 0, ())
    return base, (0, 0, patch + 1, ())


def _tilde_bounds(base: SemverTuple) -> tuple[SemverTuple, SemverTuple]:
    major, minor, patch, _ = base
    return base, (major, minor + 1, 0, ())


def _single_comparator_bounds(token: str) -> Optional[list[tuple[str, SemverTuple]]]:
    """One comparator (e.g. ">=1.2.3", "^1.2.3", "1.2.x") -> a list of
    (op, bound) constraints, all of which must hold (AND)."""
    token = token.strip()
    if not token:
        return None

    for prefix, kind in ((">=", "gte"), ("<=", "lte"), (">", "gt"), ("<", "lt"), ("=", "eq")):
        if token.startswith(prefix):
            rest = token[len(prefix):].strip()
            exact = parse_semver(rest)
            if exact:
                return [(kind, exact)]
            bounds = _partial_to_bounds(rest)
            if not bounds:
                return None
            floor, ceil = bounds
            if kind == "gte":
                return [("gte", floor)]
            if kind == "lte":
                return [("lt", ceil)]
            if kind == "gt":
                return [("gte", ceil)]
            if kind == "lt":
                return [("lt", floor)]
            return [("gte", floor), ("lt", ceil)]

    if token.startswith("^"):
        base = parse_semver(token[1:].strip())
        if not base:
            bounds = _partial_to_bounds(token[1:].strip())
            if not bounds:
                return None
            base = bounds[0]
        floor, ceil = _caret_bounds(base)
        return [("gte", floor), ("lt", ceil)]

    if token.startswith("~"):
        base = parse_semver(token[1:].strip())
        if not base:
            bounds = _partial_to_bounds(token[1:].strip())
            if not bounds:
                return None
            base = bounds[0]
        floor, ceil = _tilde_bounds(base)
        return [("gte", floor), ("lt", ceil)]

    exact = parse_semver(token)
    if exact:
        return [("gte", exact), ("lt", (exact[0], exact[1], exact[2] + 1, ()))]

    bounds = _partial_to_bounds(token)
    if bounds:
        floor, ceil = bounds
        return [("gte", floor), ("lt", ceil)]

    return None


def _satisfies_and_group(version: SemverTuple, group: str) -> bool:
    if " - " in group:
        low_str, high_str = (p.strip() for p in group.split(" - ", 1))
        low = parse_semver(low_str) or (_partial_to_bounds(low_str) or (None, None))[0]
        high_bounds = parse_semver(high_str) or (_partial_to_bounds(high_str) or (None, None))[1]
        if low is None or high_bounds is None:
            return False
        return compare_semver(version, low) >= 0 and compare_semver(version, high_bounds) <= 0

    constraints: list[tuple[str, SemverTuple]] = []
    for token in group.split():
        parsed = _single_comparator_bounds(token)
        if parsed is None:
            return False
        constraints.extend(parsed)

    for op, bound in constraints:
        cmp = compare_semver(version, bound)
        if op == "gte" and cmp < 0:
            return False
        if op == "lte" and cmp > 0:
            return False
        if op == "gt" and cmp <= 0:
            return False
        if op == "lt" and cmp >= 0:
            return False
        if op == "eq" and cmp != 0:
            return False
    return True


def npm_satisfies(version: str, range_spec: str) -> bool:
    parsed = parse_semver(version)
    if parsed is None:
        return False
    range_spec = range_spec.strip()
    if not range_spec:
        return True
    return any(
        _satisfies_and_group(parsed, group.strip())
        for group in range_spec.split("||")
        if group.strip() or range_spec.strip() == ""
    )


def npm_max_satisfying(versions: list[str], range_spec: str) -> Optional[str]:
    candidates = [(v, parse_semver(v)) for v in versions]
    candidates = [(v, p) for v, p in candidates if p is not None and npm_satisfies(v, range_spec)]
    if not candidates:
        return None
    # Prefer stable (non-prerelease) matches; only fall back to a
    # prerelease if that's literally all that satisfies the range.
    stable = [(v, p) for v, p in candidates if not p[3]]
    pool = stable or candidates
    winner = pool[0]
    for item in pool[1:]:
        if compare_semver(item[1], winner[1]) > 0:
            winner = item
    return winner[0]


# ---------------------------------------------------------------------------
# PyPI / PEP 440
# ---------------------------------------------------------------------------


def python_max_satisfying(versions: list[str], specifier: str) -> Optional[str]:
    try:
        spec_set = SpecifierSet(specifier or "")
    except InvalidSpecifier:
        return None

    parsed: list[tuple[str, Version]] = []
    for v in versions:
        try:
            parsed.append((v, Version(v)))
        except InvalidVersion:
            continue

    matching = [(v, ver) for v, ver in parsed if spec_set.contains(ver, prereleases=False)]
    if not matching:
        matching = [(v, ver) for v, ver in parsed if spec_set.contains(ver, prereleases=True)]
    if not matching:
        return None
    return max(matching, key=lambda item: item[1])[0]
