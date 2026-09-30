"""Non-mutating test of whether missing tie-breakers alone visibly destabilize results."""

import asyncio

from channelscout.config import Settings
from channelscout.db import Database
from channelscout.search import SEARCH_SQL
from channelscout.seed import seed


async def main():
    db = Database(Settings().database_url.get_secret_value())
    await db.open()
    try:
        await db.migrate()
        await seed(db)
        unstable = SEARCH_SQL.replace(
            "rank DESC, posted_at DESC, chat_id ASC, message_id ASC", "rank DESC, posted_at DESC"
        )
        sequences = set()
        async with db.pool.connection() as conn:
            for _ in range(20):
                cur = await conn.execute(unstable, ("python async", 2, None, None, 100))
                sequences.add(tuple(r["message_id"] for r in await cur.fetchall()))
        print(f"20 repeated serial reads, {len(sequences)} distinct identity sequences")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
