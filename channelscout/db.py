from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class Database:
    def __init__(self, url):
        self.pool = AsyncConnectionPool(
            url, open=False, min_size=1, max_size=8, timeout=5,
            kwargs={"row_factory": dict_row, "options": "-c statement_timeout=3000"},
        )

    async def open(self):
        await self.pool.open(wait=True)

    async def close(self):
        await self.pool.close()

    async def ready(self):
        async with self.pool.connection() as conn:
            await conn.execute("SELECT 1 FROM schema_versions WHERE version = '001_initial.sql'")

    async def migrate(self):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(628416)")
                await conn.execute("CREATE TABLE IF NOT EXISTS schema_versions (version text PRIMARY KEY)")
                for path in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
                    cur = await conn.execute("SELECT 1 FROM schema_versions WHERE version=%s", (path.name,))
                    if not await cur.fetchone():
                        await conn.execute(path.read_text())
                        await conn.execute("INSERT INTO schema_versions VALUES (%s)", (path.name,))
