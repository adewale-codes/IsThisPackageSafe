from fastapi import APIRouter, HTTPException

from app.models.schemas import ScanResult
from app.services.npm_client import PackageNotFoundError
from app.services.scanner import scan_package

router = APIRouter()


@router.get("/scan/{package_name:path}", response_model=ScanResult)
async def scan(package_name: str) -> ScanResult:
    try:
        return await scan_package(package_name)
    except PackageNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Package '{package_name}' was not found on the npm registry.",
        )
