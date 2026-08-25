from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import badge, repo, scan, stats as stats_router, versions
from app.services import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    try:
        yield
    finally:
        await db.close_pool()


app = FastAPI(
    title="PackageSafe",
    description="npm package risk-scanning API",
    version="0.1.0",
    lifespan=lifespan,
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
app.include_router(stats_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
