"""Phase 12: the minimum viable persistence layer.

No previous phase ever set up Postgres despite it being in the original
stack plan - verified before writing any of this (grepped the whole repo
for postgres/psycopg/sqlalchemy/DATABASE_URL and found nothing but a
coincidental "sqlalchemy" string in a typosquat seed list). This is the
first real database in the project, and it stays deliberately small: two
tables (see stats.py), no ORM, no migrations framework - just asyncpg
against a schema simple enough not to need one.

Connects via the DATABASE_URL env var, which Railway injects automatically
once its Postgres plugin is attached to a service (a manual step on
railway.com - see the Phase 12 report for exactly what to click). If
DATABASE_URL isn't set, every function here no-ops rather than raising:

- Locally, without a database configured, the backend still runs exactly
  as it always has - stats just don't get recorded.
- This is also the deliberately simple way of not counting test/dev scans
  in the public numbers: only an environment with a real DATABASE_URL
  (in practice, only the deployed Railway service, at least initially)
  ever writes to the stats tables at all.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_stats (
    day DATE NOT NULL,
    metric TEXT NOT NULL,
    count BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (day, metric)
);

-- Solely to compute "how many distinct packages have been scanned" - no
-- timestamp, no per-package count, never exposed via the API. Storing
-- *only* identity (not when or how often) is what keeps this a distinct-
-- count primitive rather than the search-history tracking the Phase 12
-- brief explicitly ruled out.
CREATE TABLE IF NOT EXISTS seen_packages (
    ecosystem TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (ecosystem, name)
);
"""


async def init_pool() -> None:
    """Called once at app startup (see main.py's lifespan). Safe to call
    when DATABASE_URL isn't set - leaves the pool as None, and every other
    function in this module treats that as "stats recording is disabled"."""
    global _pool
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.info("DATABASE_URL not set - stats recording is disabled for this process.")
        return

    try:
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(_SCHEMA)
        logger.info("Connected to Postgres and ensured stats schema exists.")
    except Exception as exc:  # noqa: BLE001 - a stats DB outage must never take the API down with it
        logger.warning("Could not connect to Postgres (stats recording disabled): %s", exc)
        _pool = None


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> Optional[asyncpg.Pool]:
    return _pool
