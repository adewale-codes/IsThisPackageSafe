from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import badge, repo, scan, versions

app = FastAPI(
    title="PackageSafe",
    description="npm package risk-scanning API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router)
app.include_router(badge.router)
app.include_router(versions.router)
app.include_router(repo.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
