from fastapi import APIRouter, HTTPException

from app.models.schemas import Ecosystem, ScanResult
from app.services.ecosystems import PackageNotFoundError
from app.services.scanner import scan_package

router = APIRouter()


async def _scan(ecosystem: Ecosystem, package_identifier: str) -> ScanResult:
    try:
        return await scan_package(ecosystem, package_identifier)
    except PackageNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Package '{package_identifier}' was not found in the {ecosystem} registry.",
        )
    except ValueError as exc:
        # e.g. a malformed Maven "groupId:artifactId" coordinate.
        raise HTTPException(status_code=400, detail=str(exc))


# Explicit, literal-prefixed routes registered before the legacy catch-all
# below - Starlette matches routes in registration order, and a single
# {ecosystem} path param can't safely disambiguate "/scan/npm/axios" from
# "/scan/@babel/core" (a genuine two-segment npm scoped-package path) since
# uvicorn decodes %2F to a literal "/" before the router ever sees it.
@router.get("/scan/npm/{package_identifier:path}", response_model=ScanResult)
async def scan_npm(package_identifier: str) -> ScanResult:
    return await _scan("npm", package_identifier)


@router.get("/scan/pypi/{package_identifier:path}", response_model=ScanResult)
async def scan_pypi(package_identifier: str) -> ScanResult:
    return await _scan("pypi", package_identifier)


@router.get("/scan/maven/{package_identifier:path}", response_model=ScanResult)
async def scan_maven(package_identifier: str) -> ScanResult:
    return await _scan("maven", package_identifier)


# Legacy alias for ecosystem=npm, kept so Phase 2's CLI and Phase 3's
# website don't break before they're updated in this same phase.
@router.get("/scan/{package_identifier:path}", response_model=ScanResult)
async def scan_legacy(package_identifier: str) -> ScanResult:
    return await _scan("npm", package_identifier)
