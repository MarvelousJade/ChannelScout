"""Baseline regressions also used as the learning exercises' acceptance checks."""

import asyncio

from psycopg import AsyncConnection

from channelscout.ingestion import Ingestor
from channelscout.search import SearchRequest, page, search
from channelscout.seed import seed
from test_ingestion import post, stored


async def test_exercise_a_concurrent_delivery(db, monkeypatch):
    original = AsyncConnection.execute
    receipt_barrier = asyncio.Barrier(2)
    post_barrier = asyncio.Barrier(2)

    async def scheduled_execute(conn, query, *args, **kwargs):
        result = await original(conn, query, *args, **kwargs)
        # Deterministic concurrent schedule for receipt reads, if this code path exists.
        if isinstance(query, str) and query.strip().startswith("SELECT 1 FROM processed_updates"):
            await asyncio.wait_for(receipt_barrier.wait(), timeout=5)
        if isinstance(query, str) and query.strip().startswith("SELECT 1 FROM posts"):
            await asyncio.wait_for(post_barrier.wait(), timeout=5)
        return result

    monkeypatch.setattr(AsyncConnection, "execute", scheduled_execute)
    worker = Ingestor(db, {-100123})
    await asyncio.gather(worker.process(post()), worker.process(post()))
    async with db.pool.connection() as conn:
        cur = await conn.execute("SELECT count(*) AS n FROM processed_updates")
        receipt_count = (await cur.fetchone())["n"]
    assert (receipt_count, len(await stored(db))) == (1, 1)


async def test_exercise_b_delayed_event(db):
    worker = Ingestor(db, {-100123})
    await worker.process(post(2, "Corrected coroutine examples", edit=1700000200))
    await worker.process(post(3, "Outdated coroutine examples", edit=1700000100))
    assert (await stored(db))[0]["body"] == "Corrected coroutine examples"


async def test_exercise_c_page_boundaries(db):
    await seed(db)
    async with db.pool.connection() as conn:
        results = await search(conn, SearchRequest("python async"))
    assert results[0]["rank"] == results[14]["rank"]
    assert results[0]["posted_at"] == results[14]["posted_at"]
    pages = [page(results, index) for index in range(3)]
    identities = [(row["chat_id"], row["message_id"]) for subset in pages for row in subset]
    assert len(identities) == len(set(identities))
    assert identities == [(r["chat_id"], r["message_id"]) for r in results[:15]]
