"""Synthetic corpus: 30 topics, interleaved identities, repetitions and 1000 edits."""

from datetime import datetime, timedelta, timezone

TOPICS = [
    "python async",
    "postgres index",
    "docker compose",
    "fastapi testing",
    "telegram bot",
    "git branching",
    "linux shell",
    "redis cache",
    "javascript promise",
    "typescript types",
    "rust ownership",
    "java threads",
    "csharp linq",
    "golang channels",
    "kubernetes pods",
    "http caching",
    "oauth security",
    "pytest fixtures",
    "sql joins",
    "react hooks",
    "node streams",
    "graphql schema",
    "ci deployment",
    "regex parsing",
    "data structures",
    "binary search",
    "network sockets",
    "database transactions",
    "logging metrics",
    "api pagination",
]


def rows(count=10000):
    origin = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(1, count + 1):
        topic = TOPICS[(i - 1) % len(TOPICS)]
        day = origin + timedelta(days=i % 90)
        edited = i % 10 == 0
        repetition = (" " + topic) * (i % 3)
        body = f"{topic}: developer resource with tutorial, examples and practical exercises.{repetition}"
        if i % 7 == 0:
            # Mention-only marketing distractors, not useful developer resources.
            body = (topic + " ") * 4 + ("newsletter announcement promotion subscribe today " * 16)
        if edited:
            body += " Revised examples after review."
        yield (
            -100999,
            i,
            "Synthetic Developer Resources",
            "synthetic_not_live",
            day,
            body,
            day + timedelta(hours=int(edited)),
            i + 10000 * int(edited),
        )


async def seed(db):
    async with db.pool.connection() as conn:
        async with conn.transaction():
            # Isolated synthetic channel; does not erase real channel records.
            await conn.execute("DELETE FROM posts WHERE chat_id = -100999")
            async with conn.cursor() as cur:
                await cur.executemany(
                    """INSERT INTO posts
                    (chat_id,message_id,channel_name,username,posted_at,body,event_at,event_update_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    rows(),
                )
        await conn.execute("ANALYZE posts")
