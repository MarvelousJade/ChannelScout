from unittest.mock import AsyncMock

import httpx
import pytest
from telegram import Update
from telegram.error import RetryAfter, TimedOut, Forbidden

from channelscout.app import create_app
from channelscout.commands import Commands
from channelscout.config import Settings
from channelscout.ingestion import Ingestor
from channelscout.seed import seed
from channelscout.transport import deliver_one, poll


def command(text, uid=100, user=42):
    return Update.de_json(
        {
            "update_id": uid,
            "message": {
                "message_id": uid,
                "date": 1700000000,
                "chat": {"id": user, "type": "private"},
                "from": {"id": user, "is_bot": False, "first_name": "Tester"},
                "text": text,
            },
        },
        None,
    )


def callback(data, uid=101, user=42):
    return Update.de_json(
        {
            "update_id": uid,
            "callback_query": {
                "id": str(uid),
                "data": data,
                "chat_instance": "instance",
                "from": {"id": user, "is_bot": False, "first_name": "Tester"},
            },
        },
        None,
    )


async def queued(db, uid):
    async with db.pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM outbox WHERE update_id=%s", (uid,))
        return await cur.fetchone()


async def test_commands_snapshot_navigation_ownership(db):
    await seed(db)
    worker = Ingestor(db, set(), Commands())
    for uid, text in enumerate(["/start", "/help", "/search", "/search nonexistentzzzz"], 1):
        await worker.process(command(text, uid))
        assert (await queued(db, uid))["payload"][0]["text"]
    await worker.process(command("/search python async"))
    first = (await queued(db, 100))["payload"][0]
    assert "https://t.me/" in first["text"]
    assert "2025-" in first["text"]
    next_data = first["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    # A live edit/delete must not move stored page boundaries.
    async with db.pool.connection() as conn:
        await conn.execute("DELETE FROM posts")
    await worker.process(callback(next_data))
    second = (await queued(db, 101))["payload"][1]
    assert "Results 6–10" in second["text"]
    prev_data = second["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    await worker.process(callback(prev_data, 102))
    assert (await queued(db, 102))["payload"][1]["text"] == first["text"]
    await worker.process(callback(next_data, 103, user=55))
    assert "expired" in (await queued(db, 103))["payload"][0]["text"]
    async with db.pool.connection() as conn:
        await conn.execute("UPDATE search_sessions SET expires_at=now()-interval '1 second'")
    await worker.process(callback(next_data, 104))
    assert "expired" in (await queued(db, 104))["payload"][0]["text"]
    assert not await worker.process(command("/search python async"))


async def test_delivery_retry_after_recovery_and_terminal_failure(db):
    worker = Ingestor(db, set(), Commands())
    await worker.process(command("/help"))
    bot = AsyncMock()
    bot.send_message.side_effect = RetryAfter(30)
    assert await deliver_one(db, bot)
    assert not await deliver_one(db, bot)
    item = await queued(db, 100)
    assert item["attempts"] == 1 and item["sent_at"] is None
    async with db.pool.connection() as conn:
        cur = await conn.execute(
            "SELECT available_at >= now()+interval '28 seconds' AS respected FROM outbox"
        )
        assert (await cur.fetchone())["respected"]
        await conn.execute("UPDATE outbox SET available_at=now()")
    bot.send_message.side_effect = None
    assert await deliver_one(db, bot)
    assert (await queued(db, 100))["sent_at"]
    await worker.process(command("/help", 101))
    bot.send_message.side_effect = Forbidden("blocked")
    await deliver_one(db, bot)
    assert (await queued(db, 101))["failed_at"]
    await worker.process(command("/help", 102))
    bot.send_message.side_effect = TimedOut()
    for _ in range(5):
        async with db.pool.connection() as conn:
            await conn.execute("UPDATE outbox SET available_at=now() WHERE update_id=102")
        await deliver_one(db, bot)
    assert (await queued(db, 102))["attempts"] == 5
    assert (await queued(db, 102))["failed_at"]


async def test_webhook_auth_replay_and_failure_recovery(db):
    s = Settings(
        _env_file=None,
        mode="webhook",
        telegram_token="x",
        webhook_secret="demo-secret",
        webhook_url="https://demo.example/telegram/webhook",
    )
    app = create_app(s, db)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        assert (await c.get("/ready")).status_code == 200
        assert (await c.post("/telegram/webhook", json={"update_id": 1})).status_code == 403
        headers = {"X-Telegram-Bot-Api-Secret-Token": "demo-secret"}
        assert (
            await c.post("/telegram/webhook", content="invalid", headers=headers)
        ).status_code == 400
        assert (
            await c.post("/telegram/webhook", json={"update_id": "1"}, headers=headers)
        ).status_code == 400
        payload = command("/help").to_dict()
        for _ in range(2):
            assert (
                await c.post("/telegram/webhook", json=payload, headers=headers)
            ).status_code == 200
        assert (await queued(db, 100))["attempts"] == 0
        original = db.pool.connection

        def broken():
            raise RuntimeError("database unavailable")

        db.pool.connection = broken
        assert (
            await c.post("/telegram/webhook", json={"update_id": 101}, headers=headers)
        ).status_code == 503
        db.pool.connection = original
        assert (
            await c.post("/telegram/webhook", json={"update_id": 101}, headers=headers)
        ).status_code == 200


async def test_poll_confirms_only_committed_update():
    bot = AsyncMock()
    worker = AsyncMock()
    bot.get_updates.side_effect = [[command("/help")], []]
    import asyncio

    task = asyncio.create_task(poll(bot, worker))
    for _ in range(100):
        if bot.get_updates.call_count >= 2:
            break
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert bot.get_updates.call_args_list[0].kwargs["offset"] is None
    assert bot.get_updates.call_args_list[1].kwargs["offset"] == 101
