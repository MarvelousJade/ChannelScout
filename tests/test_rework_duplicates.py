import asyncio

from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import AsyncConnection, sql
from psycopg.errors import ForeignKeyViolation, UniqueViolation

from channelscout import db as db_module

from channelscout.ingestion import Ingestor
from test_ingestion import post, stored


async def test_distinct_updates_share_one_post_identity(db, monkeypatch):
    """Receipt dedup alone must not allow two rows for the same post."""
    original = AsyncConnection.execute
    both_read_absence = asyncio.Barrier(2)

    async def overlapping_reads(conn, query, *args, **kwargs):
        cursor = await original(conn, query, *args, **kwargs)
        if isinstance(query, str) and query.strip().startswith("SELECT 1 FROM posts"):
            await asyncio.wait_for(both_read_absence.wait(), 5)
        return cursor

    monkeypatch.setattr(AsyncConnection, "execute", overlapping_reads)
    worker = Ingestor(db, {-100123})
    assert await asyncio.gather(worker.process(post(10)), worker.process(post(11))) == [True, True]
    assert len(await stored(db)) == 1
    async with db.pool.connection() as conn:
        cursor = await conn.execute("SELECT count(*) AS n FROM processed_updates")
        assert (await cursor.fetchone())["n"] == 2


async def test_forward_migration_archives_duplicates_and_restores_constraints(db):
    """Recreate a damaged 004 schema without damaging the shared test schema."""
    migrations = Path(db_module.__file__).with_name("migrations")
    schema = sql.Identifier("repair_" + uuid4().hex)
    async with db.pool.connection() as conn:
        async with conn.transaction(force_rollback=True):
            await conn.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
            await conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(schema))
            for name in [
                "001_initial.sql",
                "002_snapshot.sql",
                "003_delivery.sql",
                "004_learning_checkpoint.sql",
            ]:
                await conn.execute((migrations / name).read_text())
            insert = """INSERT INTO posts(chat_id,message_id,channel_name,username,posted_at,
                        body,event_at,event_update_id)
                        VALUES (-100123,%s,'Demo','demo','2025-01-01',%s,%s,%s)"""
            for message_id, body, event_at, update_id in [
                (7, "old", "2025-01-01", 99),
                (7, "intermediate", "2025-01-03", 2),
                (7, "a-ambiguous", "2025-01-03", 3),
                (7, "z-corrected", "2025-01-03", 3),
                (8, "unrelated", "2025-01-01", 1),
            ]:
                await conn.execute(insert, (message_id, body, event_at, update_id))
            await conn.execute("""INSERT INTO processed_updates VALUES
                                  (1000,'2025-01-02'),(1000,'2025-01-01'),(2000,'2025-01-01')""")
            await conn.execute("INSERT INTO outbox(update_id,payload) VALUES (1000,'[]')")
            await conn.execute((migrations / "005_restore_ingestion_identity.sql").read_text())
            cur = await conn.execute("SELECT body FROM posts ORDER BY message_id")
            assert [row["body"] for row in await cur.fetchall()] == ["z-corrected", "unrelated"]
            cur = await conn.execute(
                "SELECT source_table,original_record FROM ingestion_repair_archive"
            )
            archived = await cur.fetchall()
            assert len(archived) == 4
            assert {
                r["original_record"]["body"] for r in archived if r["source_table"] == "posts"
            } == {"old", "intermediate", "a-ambiguous"}
            cur = await conn.execute(
                "SELECT processed_at::text AS at FROM processed_updates WHERE update_id=1000"
            )
            assert (await cur.fetchone())["at"].startswith("2025-01-01")
            cur = await conn.execute("SELECT update_id,payload,attempts,sent_at FROM outbox")
            assert await cur.fetchall() == [
                {"update_id": 1000, "payload": [], "attempts": 0, "sent_at": None}
            ]
            for statement, params, exception in [
                (insert, (7, "duplicate", "2025-01-04", 4), UniqueViolation),
                ("INSERT INTO processed_updates(update_id) VALUES (1000)", (), UniqueViolation),
                (
                    "INSERT INTO outbox(update_id,payload) VALUES (9999,'[]')",
                    (),
                    ForeignKeyViolation,
                ),
            ]:
                with pytest.raises(exception):
                    async with conn.transaction():
                        await conn.execute(statement, params)


async def test_failed_repair_rolls_back_archival_and_changes(db):
    """An orphaned outbox causes FK restoration to fail; migration must not partially clean data."""
    migrations = Path(db_module.__file__).with_name("migrations")
    schema = sql.Identifier("repair_" + uuid4().hex)
    async with db.pool.connection() as conn:
        async with conn.transaction(force_rollback=True):
            await conn.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
            await conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(schema))
            for name in [
                "001_initial.sql",
                "002_snapshot.sql",
                "003_delivery.sql",
                "004_learning_checkpoint.sql",
            ]:
                await conn.execute((migrations / name).read_text())
            await conn.execute("INSERT INTO processed_updates(update_id) VALUES (1),(1)")
            await conn.execute("INSERT INTO outbox(update_id,payload) VALUES (9999,'[]')")
            with pytest.raises(ForeignKeyViolation):
                async with conn.transaction():
                    await conn.execute(
                        (migrations / "005_restore_ingestion_identity.sql").read_text()
                    )
            cur = await conn.execute("SELECT count(*) AS n FROM processed_updates")
            assert (await cur.fetchone())["n"] == 2
            cur = await conn.execute("SELECT to_regclass('ingestion_repair_archive') AS archive")
            assert (await cur.fetchone())["archive"] is None
