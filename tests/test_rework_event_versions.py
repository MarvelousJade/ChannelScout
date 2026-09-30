import asyncio

from channelscout.ingestion import Ingestor
from test_ingestion import post, stored


async def test_same_second_lower_update_id_cannot_revert_edit(db):
    worker = Ingestor(db, {-100123})
    await worker.process(post(8, "latest same-second revision", edit=1700000200))
    await worker.process(post(7, "older same-second revision", edit=1700000200))
    row = (await stored(db))[0]
    assert row["body"] == "latest same-second revision"
    assert row["event_update_id"] == 8


async def test_concurrent_older_versions_cannot_replace_newest(db):
    worker = Ingestor(db, {-100123})
    await worker.process(post(50, "winning revision", edit=1700000300))
    initial_date = (await stored(db))[0]["posted_at"]
    assert await asyncio.gather(
        worker.process(post(99, "older timestamp but higher ID", edit=1700000200)),
        worker.process(post(49, "lower ID in the same second", edit=1700000300)),
        worker.process(post(100, "delayed original")),
    ) == [True, True, True]
    row = (await stored(db))[0]
    assert row["body"] == "winning revision"
    assert row["event_update_id"] == 50
    assert row["posted_at"] == initial_date
    async with db.pool.connection() as conn:
        cur = await conn.execute("SELECT count(*) AS n FROM processed_updates")
        assert (await cur.fetchone())["n"] == 4


async def test_timestamp_takes_priority_over_update_id(db):
    worker = Ingestor(db, {-100123})
    await worker.process(post(50, "prior revision", edit=1700000200))
    await worker.process(post(2, "later timestamp with lower ID", edit=1700000300))
    row = (await stored(db))[0]
    assert row["body"] == "later timestamp with lower ID"
    assert row["event_update_id"] == 2
