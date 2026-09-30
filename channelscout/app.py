import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import Settings

log = logging.getLogger("channelscout")


def event(name: str, **fields):
    # Deliberate whitelist: never log bodies, tokens, URLs or exception messages.
    log.info(json.dumps({"event": name, **fields}))


def create_app(settings=None, database=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        event("service_started", mode=settings.mode)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "alive"}

    @app.get("/ready")
    async def ready():
        try:
            if database is None:
                raise RuntimeError("database not connected")
            await database.ready()
            return {"status": "ready"}
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)

    return app


app = create_app()
