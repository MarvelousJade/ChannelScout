import asyncio
from datetime import timedelta
import logging

from telegram import Update, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.error import BadRequest, NetworkError, RetryAfter, TelegramError

ALLOWED_UPDATES = ["channel_post", "edited_channel_post", "message", "callback_query"]
log = logging.getLogger("channelscout")


def retry_seconds(error, attempts):
    if isinstance(error, RetryAfter):
        delay = error.retry_after
        return delay.total_seconds() if isinstance(delay, timedelta) else float(delay)
    return min(2**attempts, 60)


async def deliver_one(db, bot):
    # One service, durable queue, DB row lock across bounded Telegram requests.
    async with db.pool.connection() as conn:
        async with conn.transaction():
            cur = await conn.execute("""SELECT * FROM outbox
                WHERE sent_at IS NULL AND failed_at IS NULL AND available_at <= now()
                ORDER BY available_at, update_id FOR UPDATE SKIP LOCKED LIMIT 1""")
            item = await cur.fetchone()
            if not item:
                return False
            attempts = item["attempts"] + 1
            try:
                for action in item["payload"]:
                    kwargs = dict(action)
                    method = kwargs.pop("method")
                    if "reply_markup" in kwargs:
                        kwargs["reply_markup"] = InlineKeyboardMarkup.de_json(
                            kwargs["reply_markup"], bot
                        )
                    if "link_preview_options" in kwargs:
                        kwargs["link_preview_options"] = LinkPreviewOptions.de_json(
                            kwargs["link_preview_options"], bot
                        )
                    try:
                        async with asyncio.timeout(12):
                            await getattr(bot, method)(
                                **kwargs,
                                read_timeout=5,
                                write_timeout=5,
                                connect_timeout=5,
                                pool_timeout=5,
                            )
                    except BadRequest:
                        # Expired callback acknowledgement must not block the actual reply.
                        if method != "answer_callback_query":
                            raise
                await conn.execute(
                    "UPDATE outbox SET sent_at=now(), attempts=%s WHERE update_id=%s",
                    (attempts, item["update_id"]),
                )
            except (TelegramError, TimeoutError) as error:
                retryable = isinstance(error, (NetworkError, RetryAfter, TimeoutError))
                delay = retry_seconds(error, attempts)
                await conn.execute(
                    """UPDATE outbox SET attempts=%s, last_error_class=%s,
                    available_at=now() + %s * interval '1 second',
                    failed_at=CASE WHEN %s THEN now() ELSE NULL END WHERE update_id=%s""",
                    (
                        attempts,
                        type(error).__name__,
                        delay,
                        not retryable or attempts >= 5,
                        item["update_id"],
                    ),
                )
                log.warning('{"event":"delivery_failed","error_class":"%s"}', type(error).__name__)
    return True


async def delivery_loop(db, bot):
    while True:
        try:
            if not await deliver_one(db, bot):
                await asyncio.sleep(0.5)
        except Exception as error:
            log.warning('{"event":"worker_retry","error_class":"%s"}', type(error).__name__)
            await asyncio.sleep(2)


async def poll(bot, ingestor):
    # Telegram confirms updates only on the NEXT getUpdates request using offset.
    offset = None
    while True:
        try:
            updates = await bot.get_updates(
                offset=offset,
                timeout=20,
                allowed_updates=ALLOWED_UPDATES,
                read_timeout=25,
                connect_timeout=5,
                write_timeout=5,
                pool_timeout=5,
            )
            for update in updates:
                await ingestor.process(update)
                offset = update.update_id + 1
        except RetryAfter as error:
            await asyncio.sleep(retry_seconds(error, 1))
        except Exception as error:
            log.warning('{"event":"poll_retry","error_class":"%s"}', type(error).__name__)
            await asyncio.sleep(2)


def decode_update(payload, bot=None):
    if not isinstance(payload, dict) or type(payload.get("update_id")) is not int:
        raise ValueError("Invalid update envelope")
    return Update.de_json(payload, bot)
