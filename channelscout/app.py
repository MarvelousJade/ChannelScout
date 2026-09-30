import json
import logging
import asyncio
import hmac
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from telegram import Bot
from telegram.request import HTTPXRequest

from .db import Database
from .commands import Commands
from .ingestion import Ingestor
from .transport import ALLOWED_UPDATES, decode_update, delivery_loop, poll
from fastapi.responses import JSONResponse

from .config import Settings

log = logging.getLogger("channelscout")


def event(name: str, **fields):
    # Deliberate whitelist: never log bodies, tokens, URLs or exception messages.
    log.info(json.dumps({"event": name, **fields}))


def create_app(settings=None, database=None, bot=None):
    settings = settings or Settings()
    db = database or Database(settings.database_url.get_secret_value())
    ingestor = Ingestor(db, settings.allowlist, Commands())

    @asynccontextmanager
    async def lifespan(app):
        tasks = []
        active_bot = bot
        await db.open()
        try:
            await db.migrate()
            if settings.mode != "off":
                active_bot = active_bot or Bot(
                    settings.telegram_token.get_secret_value(),
                    request=HTTPXRequest(connect_timeout=5, read_timeout=5, write_timeout=5),
                )
                await active_bot.initialize()
                if settings.mode == "polling":
                    await active_bot.delete_webhook(drop_pending_updates=False)
                    tasks.append(asyncio.create_task(poll(active_bot, ingestor)))
                else:
                    await active_bot.set_webhook(
                        url=settings.webhook_url,
                        secret_token=settings.webhook_secret.get_secret_value(),
                        allowed_updates=ALLOWED_UPDATES,
                        drop_pending_updates=False,
                    )
                tasks.append(asyncio.create_task(delivery_loop(db, active_bot)))
            event("service_started", mode=settings.mode)
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError):
                    await task
            if active_bot:
                await active_bot.shutdown()
            await db.close()

    app = FastAPI(lifespan=lifespan)

    @app.post("/telegram/webhook")
    async def webhook(request: Request):
        if settings.mode != "webhook":
            return JSONResponse({"error": "disabled"}, status_code=404)
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(
            supplied.encode(), settings.webhook_secret.get_secret_value().encode()
        ):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        data = await request.body()
        if len(data) > 1024 * 1024:
            return JSONResponse({"error": "too_large"}, status_code=413)
        try:
            update = decode_update(json.loads(data))
        except (ValueError, TypeError, KeyError, AttributeError):
            return JSONResponse({"error": "invalid_update"}, status_code=400)
        try:
            await ingestor.process(update)
        except Exception as error:
            event("processing_failed", error_class=type(error).__name__)
            return JSONResponse({"error": "temporarily_unavailable"}, status_code=503)
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "alive"}

    @app.get("/ready")
    async def ready():
        try:
            await db.ready()
            return {"status": "ready"}
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)

    return app


app = create_app()
