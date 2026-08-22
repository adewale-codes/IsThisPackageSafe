from typing import Optional, Union

from fastapi import APIRouter, HTTPException

from app.models.schemas import DependencyTree, Ecosystem, ScanResult
from app.services.dependency_tree import DEFAULT_MAX_DEPTH, DEFAULT_NODE_CAP, build_dependency_tree
from app.services.ecosystems import PackageNotFoundError
from app.services.scanner import scan_package

router = APIRouter()


async def _scan(
    ecosystem: Ecosystem,
    package_identifier: str,
    version: Optional[str] = None,
    *,
    include_tree: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_cap: int = DEFAULT_NODE_CAP,
) -> Union[ScanResult, DependencyTree]:
    try:
        if include_tree:
            return await build_dependency_tree(
                ecosystem, package_identifier, version, max_depth=max_depth, node_cap=node_cap
            )
        return await scan_package(ecosystem, package_identifier, version)
    except PackageNotFoundError:
        display_name = f"{package_identifier}@{version}" if version else package_identifier
        raise HTTPException(
            status_code=404,
            detail=f"Package '{display_name}' was not found in the {ecosystem} registry.",
        )
    except ValueError as exc:
        # e.g. a malformed Maven "groupId:artifactId" coordinate.
        raise HTTPException(status_code=400, detail=str(exc))


# version, include_tree, max_depth, and node_cap (Phase 8) are query params
# rather than extra path segments - a path-based /scan/{ecosystem}/{package}
# /{version} route isn't achievable here: {package_identifier:path} must
# stay a greedy, last-in-pattern matcher for scoped npm packages
# (e.g. "@babel/core"), and Starlette path converters can't be followed by
# another path segment. Query params sidestep that entirely.
#
# Explicit, literal-prefixed routes registered before the legacy catch-all
# below - Starlette matches routes in registration order, and a single
# {ecosystem} path param can't safely disambiguate "/scan/npm/axios" from
# "/scan/@babel/core" (a genuine two-segment npm scoped-package path) since
# uvicorn decodes %2F to a literal "/" before the router ever sees it.
@router.get("/scan/npm/{package_identifier:path}", response_model=Union[ScanResult, DependencyTree])
async def scan_npm(
    package_identifier: str,
    version: Optional[str] = None,
    include_tree: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_cap: int = DEFAULT_NODE_CAP,
) -> Union[ScanResult, DependencyTree]:
    return await _scan(
        "npm", package_identifier, version, include_tree=include_tree, max_depth=max_depth, node_cap=node_cap
    )


@router.get("/scan/pypi/{package_identifier:path}", response_model=Union[ScanResult, DependencyTree])
async def scan_pypi(
    package_identifier: str,
    version: Optional[str] = None,
    include_tree: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_cap: int = DEFAULT_NODE_CAP,
) -> Union[ScanResult, DependencyTree]:
    return await _scan(
        "pypi", package_identifier, version, include_tree=include_tree, max_depth=max_depth, node_cap=node_cap
    )


@router.get("/scan/maven/{package_identifier:path}", response_model=Union[ScanResult, DependencyTree])
async def scan_maven(
    package_identifier: str,
    version: Optional[str] = None,
    include_tree: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_cap: int = DEFAULT_NODE_CAP,
) -> Union[ScanResult, DependencyTree]:
    return await _scan(
        "maven", package_identifier, version, include_tree=include_tree, max_depth=max_depth, node_cap=node_cap
    )


# Legacy alias for ecosystem=npm, kept so Phase 2's CLI and Phase 3's
# website don't break before they're updated in this same phase.
@router.get("/scan/{package_identifier:path}", response_model=Union[ScanResult, DependencyTree])
async def scan_legacy(
    package_identifier: str,
    version: Optional[str] = None,
    include_tree: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_cap: int = DEFAULT_NODE_CAP,
) -> Union[ScanResult, DependencyTree]:
    return await _scan(
        "npm", package_identifier, version, include_tree=include_tree, max_depth=max_depth, node_cap=node_cap
    )
