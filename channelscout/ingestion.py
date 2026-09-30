"""Update receipt and post mutation are one database transaction."""

from telegram import Update
from psycopg.types.json import Jsonb


INSERT_POST = """INSERT INTO posts
    (chat_id,message_id,channel_name,username,posted_at,body,event_at,event_update_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
UPDATE_POST = """UPDATE posts SET channel_name=%s, username=%s, body=%s,
    event_at=%s, event_update_id=%s WHERE chat_id=%s AND message_id=%s
    AND (%s, %s) > (event_at, event_update_id)"""


async def store_post(conn, values):
    cur = await conn.execute("SELECT 1 FROM posts WHERE chat_id=%s AND message_id=%s", values[:2])
    if await cur.fetchone():
        await conn.execute(
            UPDATE_POST,
            (
                values[2],
                values[3],
                values[5],
                values[6],
                values[7],
                values[0],
                values[1],
                values[6],
                values[7],
            ),
        )
    else:
        await conn.execute(INSERT_POST, values)


class Ingestor:
    def __init__(self, db, allowlist, commands=None):
        self.db, self.allowlist, self.commands = db, allowlist, commands

    async def process(self, update: Update):
        async with self.db.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    "SELECT 1 FROM processed_updates WHERE update_id=%s", (update.update_id,)
                )
                if await cur.fetchone():
                    return False
                await conn.execute(
                    "INSERT INTO processed_updates(update_id) VALUES (%s)", (update.update_id,)
                )
                post = update.edited_channel_post or update.channel_post
                if post and post.chat.id in self.allowlist and post.chat.type == "channel":
                    if post.chat.username:
                        await store_post(
                            conn,
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
