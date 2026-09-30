"""Upgrade a known baseline schema in an EMPTY disposable database, preserving its data."""

import argparse
import asyncio
import json
import subprocess

from psycopg import sql

from channelscout.config import Settings
from channelscout.db import Database
from channelscout.seed import seed


async def fingerprints(db):
    result = {}
    async with db.pool.connection() as conn:
        for table in ["posts", "processed_updates", "outbox", "search_sessions"]:
            cur = await conn.execute(
                sql.SQL("""SELECT count(*) AS count,
                md5(string_agg(to_jsonb(t)::text, E'\\n' ORDER BY to_jsonb(t)::text)) AS hash
                FROM {} t""").format(sql.Identifier(table))
            )
            result[table] = await cur.fetchone()
    return result


async def main(baseline):
    db = Database(Settings().database_url.get_secret_value())
    await db.open()
    try:
        async with db.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema='public'"
            )
            if await cur.fetchone():
                raise RuntimeError("Refusing nonempty database: use a NEW disposable database")
            await conn.execute("CREATE TABLE schema_versions(version text PRIMARY KEY)")
            for name in ["001_initial.sql", "002_snapshot.sql", "003_delivery.sql"]:
                body = subprocess.check_output(
                    ["git", "show", f"{baseline}:channelscout/migrations/{name}"], text=True
                )
                await conn.execute(body)
                await conn.execute("INSERT INTO schema_versions VALUES (%s)", (name,))
        await seed(db)
        async with db.pool.connection() as conn:
            await conn.execute("INSERT INTO processed_updates(update_id) VALUES (88000)")
            await conn.execute("INSERT INTO outbox(update_id,payload) VALUES (88000,'[]')")
            await conn.execute("""INSERT INTO search_sessions(id,owner_id,query,results)
                VALUES ('baseline-probe',42,'python async','[]')""")
        before = await fingerprints(db)
        await db.migrate()
        await db.migrate()  # idempotent second startup
        await db.ready()
        after = await fingerprints(db)
        if before != after:
            raise AssertionError("Baseline data changed during upgrade")
        async with db.pool.connection() as conn:
            cur = await conn.execute("SELECT count(*) AS count FROM ingestion_repair_archive")
            if (await cur.fetchone())["count"]:
                raise AssertionError("Pristine baseline unexpectedly required deduplication")
        print(
            json.dumps(
                {
                    "baseline": baseline,
                    "data_preserved": True,
                    "before": before,
                    "after": after,
                    "archived_rows": 0,
                },
                indent=2,
            )
        )
    finally:
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="800fcba")
    asyncio.run(main(parser.parse_args().baseline))
