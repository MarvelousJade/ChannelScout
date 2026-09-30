import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from telegram import Bot
from telegram.request import BaseRequest
from telegram.error import RetryAfter
from psycopg.errors import QueryCanceled

from channelscout.commands import Commands
from channelscout.ingestion import Ingestor
from channelscout.transport import deliver_one
from test_bot import command, queued


class FakeTelegram(BaseRequest):
    @property
    def read_timeout(self):
        return 5

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def do_request(self, url, method, request_data=None, **kwargs):
        if url.endswith("/getMe"):
            result = {"id": 1, "is_bot": True, "first_name": "Scout", "username": "ScoutBot"}
        else:
            # Validate actual PTB serialization rather than accepting any AsyncMock arguments.
            params = request_data.json_parameters
            assert params["chat_id"] == "42"
            assert json.loads(params["link_preview_options"]) == {"is_disabled": True}
            result = {
                "message_id": 1,
                "date": 1700000000,
                "chat": {"id": 42, "type": "private"},
                "text": params["text"],
            }
        return 200, json.dumps({"ok": True, "result": result}).encode()


async def test_real_library_serializes_durable_reply(db):
    await Ingestor(db, set(), Commands()).process(command("/help"))
    async with Bot("123:FAKE", request=FakeTelegram()) as bot:
        assert await deliver_one(db, bot)
    assert (await queued(db, 100))["sent_at"]


async def test_search_timeout_gets_clear_reply(db, monkeypatch):
    async def timeout(*args):
        raise QueryCanceled()

    monkeypatch.setattr("channelscout.commands.search", timeout)
    await Ingestor(db, set(), Commands()).process(command("/search python async"))
    assert "temporarily unavailable" in (await queued(db, 100))["payload"][0]["text"]


async def test_callback_rate_limit_is_not_ignored(db):
    from psycopg.types.json import Jsonb

    async with db.pool.connection() as conn:
        await conn.execute("INSERT INTO processed_updates(update_id) VALUES (100)")
        await conn.execute(
            "INSERT INTO outbox(update_id,payload) VALUES (100,%s)",
            (Jsonb([{"method": "answer_callback_query", "callback_query_id": "abc"}]),),
        )
    bot = AsyncMock()
    bot.answer_callback_query.side_effect = RetryAfter(60)
    await deliver_one(db, bot)
    assert (await queued(db, 100))["sent_at"] is None
    assert not await deliver_one(db, bot)


async def test_poll_does_not_confirm_failure(monkeypatch):
    from channelscout.transport import poll

    bot, worker = AsyncMock(), AsyncMock()
    bot.get_updates.return_value = [command("/help")]
    worker.process.side_effect = RuntimeError("commit failed")
    real_sleep = asyncio.sleep

    async def quick_sleep(seconds):
        await real_sleep(0.001)

    monkeypatch.setattr("channelscout.transport.asyncio.sleep", quick_sleep)
    task = asyncio.create_task(poll(bot, worker))
    for _ in range(100):
        if bot.get_updates.call_count >= 2:
            break
        await real_sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert bot.get_updates.call_args_list[1].kwargs["offset"] is None
