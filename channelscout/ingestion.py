"""Update receipt and post mutation are one database transaction."""

from telegram import Update
from psycopg.types.json import Jsonb


UPSERT_POST = """INSERT INTO posts
    (chat_id,message_id,channel_name,username,posted_at,body,event_at,event_update_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (chat_id,message_id) DO UPDATE SET
        channel_name=excluded.channel_name, username=excluded.username,
        body=excluded.body, event_at=excluded.event_at,
        event_update_id=excluded.event_update_id
    WHERE (excluded.event_at, excluded.event_update_id) > (posts.event_at, posts.event_update_id)
"""


class Ingestor:
    def __init__(self, db, allowlist, commands=None):
        self.db, self.allowlist, self.commands = db, allowlist, commands

    async def process(self, update: Update):
        async with self.db.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """INSERT INTO processed_updates(update_id) VALUES (%s)
                    ON CONFLICT DO NOTHING RETURNING update_id""",
                    (update.update_id,),
                )
                if not await cur.fetchone():
                    return False
                post = update.edited_channel_post or update.channel_post
                if post and post.chat.id in self.allowlist and post.chat.type == "channel":
                    # Public usernames only: no private invite links or discovery of arbitrary channels.
                    if post.chat.username:
                        await conn.execute(
                            UPSERT_POST,
                            (
                                post.chat.id,
                                post.message_id,
                                post.chat.title or post.chat.username,
                                post.chat.username,
                                post.date,
                                post.text or post.caption or "",
                                post.edit_date or post.date,
                                update.update_id,
                            ),
                        )
                if self.commands:
                    payload = await self.commands.prepare(update, conn)
                    if payload:
                        await conn.execute(
                            "INSERT INTO outbox(update_id,payload) VALUES (%s,%s)",
                            (update.update_id, Jsonb(payload)),
                        )
        return True
