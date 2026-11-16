from contextlib import asynccontextmanager

import asyncio
import logging

from app import session_store

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
CLEANUP_INTERVAL = 24 * 60 * 60

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            deleted = await asyncio.to_thread(
                session_store.cleanup_expired_sessions
            )
            logger.info(
                "Sessieopruiming voltooid. "
                "%s verlopen sessies verwijderd.",
                deleted,
            )
        except Exception:
            logger.exception("Fout tijdens de periodieke sessieopruiming.")

@asynccontextmanager
async def lifespan(app):
    deleted = await asyncio.to_thread(
        session_store.cleanup_expired_sessions
    )
    logger.info(
        "Initiële sessieopruiming voltooid. "
        "%s verlopen sessies verwijderd.",
        deleted,
    )
    cleanup_task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
