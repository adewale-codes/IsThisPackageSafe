"""Phase 9: POST /scan/repo - accepts uploaded manifest file contents (never
a server-side path, see repo_scan.py's module docstring) and returns one
aggregated RepoScanReport."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from app.models.schemas import RepoScanReport, UploadedManifest
from app.services import dependency_tree
from app.services.repo_scan import NoManifestsFoundError, scan_repo

router = APIRouter()


class RepoScanRequest(BaseModel):
    manifests: list[UploadedManifest]
    max_depth: int = Field(default=dependency_tree.DEFAULT_MAX_DEPTH, ge=0, le=6)
    node_cap: int = Field(default=dependency_tree.DEFAULT_NODE_CAP, ge=1, le=1000)


@router.post("/scan/repo", response_model=RepoScanReport)
async def scan_repo_endpoint(request: RepoScanRequest) -> RepoScanReport:
    if not request.manifests:
        raise HTTPException(status_code=400, detail="No manifest files were provided.")
    try:
        return await scan_repo(request.manifests, max_depth=request.max_depth, node_cap=request.node_cap)
    except NoManifestsFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
