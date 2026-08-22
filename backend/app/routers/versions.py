"""Phase 8: GET /versions/{ecosystem}/{package} - full version history.

A single route (not the three literal-prefixed routes scan.py uses) is safe
here: that pattern exists in scan.py only to disambiguate a *new*
ecosystem-prefixed route from the *legacy* unprefixed one. This endpoint has
no legacy alias to disambiguate against, so one {ecosystem}/{package:path}
route is unambiguous - ecosystem is a plain string, validated in the
handler rather than the route pattern.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from app.models.schemas import Ecosystem, VersionEntry
from app.services import ecosystems, scanner
from app.services.ecosystems import PackageNotFoundError

router = APIRouter()

_VALID_ECOSYSTEMS = set(ecosystems.SUPPORTED_ECOSYSTEMS)


@router.get("/versions/{ecosystem}/{package_identifier:path}", response_model=list[VersionEntry])
async def get_versions(ecosystem: str, package_identifier: str) -> list[VersionEntry]:
    if ecosystem not in _VALID_ECOSYSTEMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported ecosystem {ecosystem!r}. Supported: {', '.join(sorted(_VALID_ECOSYSTEMS))}.",
        )

    eco: Ecosystem = ecosystem  # type: ignore[assignment]
    client_impl = ecosystems.get_client(eco)

    try:
        async with httpx.AsyncClient(timeout=scanner._HTTP_TIMEOUT) as client:
            return await client_impl.fetch_version_history(client, package_identifier)
    except PackageNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Package '{package_identifier}' was not found in the {ecosystem} registry.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
