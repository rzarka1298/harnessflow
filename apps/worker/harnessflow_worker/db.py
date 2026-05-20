"""asyncpg pool helper.

Activities call into this to persist workflow_steps rows. Connection
lifecycle is owned by ``__main__``: open at startup, close on shutdown.
"""

from __future__ import annotations

import asyncpg


async def new_pool(dsn: str) -> asyncpg.Pool:
    """Open a pool against ``dsn``. Defaults sized for one local-dev worker."""
    return await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)
