import asyncio
from unittest.mock import AsyncMock

import pytest

from channelscout.app import create_app
from channelscout.config import Settings


@pytest.mark.parametrize("mode", ["polling", "webhook", "off"])
async def test_exclusive_transport_lifecycle(mode, monkeypatch):
    poll_started = asyncio.Event()

    async def polling(*args):
        poll_started.set()
        await asyncio.Event().wait()

    async def delivery(*args):
        await asyncio.Event().wait()

    monkeypatch.setattr("channelscout.app.poll", polling)
    monkeypatch.setattr("channelscout.app.delivery_loop", delivery)
    db, bot = AsyncMock(), AsyncMock()
    settings = Settings(
        _env_file=None,
        mode=mode,
        telegram_token="fake",
        webhook_url="https://demo.example/telegram/webhook",
        webhook_secret="fake-secret",
    )
    app = create_app(settings, db, bot)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0)
        assert poll_started.is_set() == (mode == "polling")
        assert bot.delete_webhook.call_count == int(mode == "polling")
        assert bot.set_webhook.call_count == int(mode == "webhook")
        assert bot.initialize.call_count == int(mode != "off")
        if mode == "webhook":
            assert bot.set_webhook.call_args.kwargs["secret_token"] == "fake-secret"
    db.close.assert_awaited_once()
