import logging
from pathlib import Path

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import Settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Arbitrary constant so concurrent backend processes never migrate at once.
MIGRATION_LOCK_ID = 7_302_001


def create_pool(settings: Settings) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        kwargs={
            **settings.database_connection_parameters(),
            "row_factory": dict_row,
        },
        min_size=1,
        max_size=5,
        # Fail fast so the Nginx proxy (5s read timeout) gets a clean 503.
        timeout=3,
        check=AsyncConnectionPool.check_connection,
        open=False,
    )


async def apply_migrations(connection: AsyncConnection) -> list[str]:
    """Apply pending SQL files in name order, each at most once."""
    applied_now: list[str] = []
    async with connection.transaction():
        await connection.execute(
            "SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,)
        )
        await connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration ("
            " version TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cursor = await connection.execute("SELECT version FROM schema_migration")
        applied = {row["version"] for row in await cursor.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in applied:
                continue
            await connection.execute(path.read_text(encoding="utf-8"))
            await connection.execute(
                "INSERT INTO schema_migration (version) VALUES (%s)",
                (path.stem,),
            )
            applied_now.append(path.stem)
    return applied_now
