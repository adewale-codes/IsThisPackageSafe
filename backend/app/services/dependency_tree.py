"""Phase 8: transitive dependency tree analysis.

Recursively scans a package's dependency graph (direct deps -> their direct
deps -> ...) up to max_depth, flagging any transitive dependency that comes
back with Findings and/or known vulnerabilities. Two performance guards
keep this bounded on real-world graphs, which are often huge and highly
diamond-shaped (the same dependency reachable via many different paths):

- Memoization by (ecosystem, name) - single-flight via asyncio Tasks, so a
  dependency reached concurrently from multiple branches is scanned exactly
  once, not once per occurrence. This relies on Python's cooperative
  (single-threaded) scheduling: the "is this already in flight" check and
  the "start scanning it" side effect happen with no `await` between them,
  so no two branches can both decide to start the same scan.
- A hard total-node cap (default 200) as a safety net against pathological
  graphs; node_cap_reached is surfaced honestly rather than silently
  truncating with no indication. A wall-clock cap on the whole walk serves
  the same purpose against one-slow-node-with-huge-fanout cases the node
  cap alone wouldn't catch quickly.

Only the ROOT package gets the full scan (heuristics + OSV + Phase 4's LLM
deep-scan, if the heuristics score warrants it). Every transitive
dependency gets heuristics + OSV only - deep-scan is deliberately not run
per node; at tree scale (dozens of nodes) that would be slow and expensive
for marginal value, and the user isn't asking "is this specific transitive
dependency malicious", just "does anything in this dependency's chain have
a known issue".

Version resolution note: neither npm's semver ranges, PyPI's version
specifiers, nor an unresolved Maven <dependency> (no explicit <version>,
inherited from a parent POM/BOM this client deliberately doesn't follow -
see ecosystems/maven.py) are resolved against what a real install would
actually pull in - that needs a full package-manager-grade resolver, out of
scope here. Every transitive dependency is instead scanned at its own
latest published version. This is a deliberate simplification: it answers
"does anything in this package's current dependency graph have a known
issue", which is the useful security signal, even though it isn't
necessarily the exact version a real install would resolve to.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from app.models.schemas import DependencyTree, Ecosystem, FlaggedDependency, ScanResult
from app.services import ecosystems, scanner

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEPTH = 3
DEFAULT_NODE_CAP = 200

# Safety net against a pathologically slow branch (e.g. a chain of Maven
# coordinates each paying search.maven.org's occasional 10s+ latency) - the
# node cap alone bounds *how many* nodes get scanned, not how long a single
# slow one (or a slow, wide fan-out of them) can take.
_TREE_BUILD_TIMEOUT = 90.0


class _TreeState:
    def __init__(self, node_cap: int) -> None:
        self.node_cap = node_cap
        self.scanned_count = 0
        self.node_cap_reached = False
        self.max_depth_reached = False
        self.memo: dict[tuple[str, str], "asyncio.Task[Optional[ScanResult]]"] = {}
        self.flagged: list[FlaggedDependency] = []
        self.flagged_names: set[str] = set()


def _dependency_names(result: ScanResult) -> list[str]:
    """Direct dependency identifiers from a ScanResult's metadata - npm,
    PyPI, and Maven all populate metadata.dependencies as
    {identifier: version_spec}, even though only npm's spec strings are
    real semver ranges (see module docstring)."""
    return list(result.metadata.dependencies.keys())


def _is_flagged(result: ScanResult) -> bool:
    return bool(result.findings) or bool(result.vulnerabilities)


async def _scan_dependency(
    client: httpx.AsyncClient, ecosystem: Ecosystem, name: str
) -> Optional[ScanResult]:
    """Scan one transitive dependency at its own latest version, heuristics
    + OSV only (no deep-scan). Returns None if it couldn't be resolved at
    all (e.g. a manifest references a package that's been unpublished, or a
    private/internal package not in the public registry) - a single
    unresolvable transitive dependency must not crash the whole tree build."""
    try:
        return await scanner._scan_with_client(
            client, ecosystem, name, None, enable_deep_scan=False
        )
    except ecosystems.PackageNotFoundError:
        return None
    except ValueError:
        # e.g. a malformed Maven coordinate somehow present in a POM.
        return None
    except Exception as exc:  # noqa: BLE001 - one bad node must not sink the tree
        logger.warning("Dependency tree: failed to scan %s:%s - %s", ecosystem, name, exc)
        return None


async def _walk(
    client: httpx.AsyncClient,
    ecosystem: Ecosystem,
    name: str,
    depth: int,
    path: list[str],
    max_depth: int,
    state: _TreeState,
) -> None:
    """Precondition: 1 <= depth <= max_depth (the caller never recurses
    past max_depth - see the `depth >= max_depth` check at the bottom)."""
    key = (ecosystem, name.lower())

    if key not in state.memo:
        if state.scanned_count >= state.node_cap:
            state.node_cap_reached = True
            return
        state.scanned_count += 1
        state.memo[key] = asyncio.ensure_future(_scan_dependency(client, ecosystem, name))

    result = await state.memo[key]
    if result is None:
        return

    current_path = path + [name]

    if _is_flagged(result) and result.package not in state.flagged_names:
        state.flagged_names.add(result.package)
        state.flagged.append(
            FlaggedDependency(
                ecosystem=ecosystem,
                package=result.package,
                version=result.resolved_version,
                path=current_path,
                risk_score=result.risk_score,
                verdict=result.verdict,
                findings=result.findings,
                vulnerabilities=result.vulnerabilities,
            )
        )

    children = _dependency_names(result)
    if depth >= max_depth:
        if children:
            # There *was* more graph below this node - we just chose not to
            # explore it. Surface that rather than looking identical to a
            # tree that's naturally shallower than max_depth.
            state.max_depth_reached = True
        return

    await asyncio.gather(
        *(
            _walk(client, ecosystem, child, depth + 1, current_path, max_depth, state)
            for child in children
        )
    )


async def build_dependency_tree(
    ecosystem: Ecosystem,
    package_identifier: str,
    version: Optional[str] = None,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_cap: int = DEFAULT_NODE_CAP,
) -> DependencyTree:
    async with httpx.AsyncClient(timeout=scanner._HTTP_TIMEOUT) as client:
        # The root always gets the full scan (deep-scan included) - the
        # node cap protects the *exploration beneath* it, not the package
        # the user actually asked to scan.
        root_result = await scanner._scan_with_client(
            client, ecosystem, package_identifier, version, enable_deep_scan=True
        )

        state = _TreeState(node_cap=node_cap)
        direct_deps = _dependency_names(root_result)

        if max_depth <= 0:
            if direct_deps:
                state.max_depth_reached = True
        else:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *(
                            _walk(client, ecosystem, dep_name, 1, [root_result.package], max_depth, state)
                            for dep_name in direct_deps
                        )
                    ),
                    timeout=_TREE_BUILD_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Dependency tree build for %s:%s timed out after %.0fs with %d node(s) scanned",
                    ecosystem,
                    package_identifier,
                    _TREE_BUILD_TIMEOUT,
                    state.scanned_count,
                )
                # asyncio.wait_for cancels the gather, but the individual
                # memoized Tasks were scheduled independently (ensure_future)
                # so they don't auto-cancel with it - stop them explicitly
                # rather than leaving them running against a client that's
                # about to close when this `async with` block exits.
                for task in state.memo.values():
                    if not task.done():
                        task.cancel()
                # A wall-clock cutoff is the same kind of safety net as the
                # node cap - reuse that flag rather than adding a new field
                # the API/UI would also need to know about.
                state.node_cap_reached = True

        return DependencyTree(
            root=root_result,
            flagged_dependencies=state.flagged,
            total_scanned=1 + state.scanned_count,
            max_depth_reached=state.max_depth_reached,
            node_cap_reached=state.node_cap_reached,
        )
