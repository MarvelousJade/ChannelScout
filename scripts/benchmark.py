"""Run only against a dedicated synthetic benchmark database, never production."""

import argparse
import asyncio
import hashlib
import json
import platform
import os
import statistics
import time
from pathlib import Path
from importlib.metadata import version

from channelscout.config import Settings
from channelscout.db import Database
from channelscout.search import SearchRequest, SEARCH_SQL, search
from channelscout.seed import seed


def percentile(values, fraction):
    return sorted(values)[int((len(values) - 1) * fraction)]


async def main(output):
    db = Database(Settings().database_url.get_secret_value())
    await db.open()
    try:
        await db.migrate()
        async with db.pool.connection() as conn:
            cur = await conn.execute("SELECT count(*) AS n FROM posts WHERE chat_id != -100999")
            if (await cur.fetchone())["n"]:
                raise RuntimeError("Use a dedicated synthetic database with no live posts")
        await seed(db)
        label_bytes = Path("evaluation/queries.json").read_bytes()
        queries = json.loads(label_bytes)["queries"]
        report = {
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "logical_cpus": os.cpu_count(),
                "packages": {p: version(p) for p in ["psycopg", "fastapi", "python-telegram-bot"]},
                "label_sha256": hashlib.sha256(label_bytes).hexdigest(),
                "posts": 10000,
                "measurement": "Local synthetic, serial, warmed; client round-trip + fetch, no Telegram or pool wait.",
            },
            "quality": {},
            "plans_and_latency": {},
        }
        async with db.pool.connection() as conn:
            cur = await conn.execute("SELECT version() AS version")
            report["environment"]["postgres"] = (await cur.fetchone())["version"]
            for norm in [0, 2, 32]:
                evaluations = []
                for label in queries:
                    results = await search(conn, SearchRequest(label["query"]), norm)
                    top = results[:5]
                    # Missing results contribute zero. No precision conditional on retrieval.
                    relevant = sum(
                        r["chat_id"] == -100999
                        and (r["message_id"] - 1) % 30 == label["topic"]
                        and r["message_id"] % 7 != 0
                        for r in top
                    )
                    evaluations.append(
                        {
                            "query": label["query"],
                            "precision_at_5": relevant / 5,
                            "top_ids": [r["message_id"] for r in top],
                        }
                    )
                report["quality"][str(norm)] = {
                    "mean_precision_at_5": statistics.mean(
                        r["precision_at_5"] for r in evaluations
                    ),
                    "queries": evaluations,
                }
            # Clear bulk-load GIN pending entries before comparing planner-selected access paths.
            await conn.execute("SELECT gin_clean_pending_list('posts_document_gin'::regclass)")
            await conn.execute("ANALYZE posts")
            report["environment"]["maintenance"] = (
                "gin_clean_pending_list and ANALYZE after bulk seed"
            )
            for indexed in [True, False]:
                # Roll back index removal: no permanent schema change. Real unindexed, not enable_seqscan=off.
                async with conn.transaction(force_rollback=True):
                    if not indexed:
                        await conn.execute("DROP INDEX posts_document_gin")
                    args = ("python async", 2, None, None, 100)
                    cur = await conn.execute(
                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + SEARCH_SQL, args
                    )
                    plan = (await cur.fetchone())["QUERY PLAN"]
                    timings = []
                    for _ in range(5):
                        await search(conn, SearchRequest("python async"), 2)
                    for _ in range(10):
                        for label in queries:
                            started = time.perf_counter()
                            await search(conn, SearchRequest(label["query"]), 2)
                            timings.append((time.perf_counter() - started) * 1000)
                    report["plans_and_latency"]["indexed" if indexed else "unindexed"] = {
                        "n": len(timings),
                        "p50_ms": statistics.median(timings),
                        "p95_ms": percentile(timings, 0.95),
                        "representative_plan": plan,
                    }
        Path(output).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: v["mean_precision_at_5"] for k, v in report["quality"].items()}))
        print(
            json.dumps(
                {
                    k: {m: v[m] for m in ["p50_ms", "p95_ms"]}
                    for k, v in report["plans_and_latency"].items()
                }
            )
        )
    finally:
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/benchmark.json")
    asyncio.run(main(parser.parse_args().output))
