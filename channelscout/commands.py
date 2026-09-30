import secrets

from psycopg.types.json import Jsonb
from psycopg.errors import QueryCanceled

from .search import PAGE_SIZE, page, parse_search, search

HELP = (
    "ChannelScout searches approved public channel posts.\n"
    "/search python async\n/search python async --since 2025-01-01\n"
    "English word matching; at most 100 results. Buttons expire after one hour."
)


def message(chat_id, text, buttons=None):
    payload = {
        "method": "send_message",
        "chat_id": chat_id,
        "text": text,
        "link_preview_options": {"is_disabled": True},
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [buttons]}
    return payload


def render(chat_id, session_id, results, index):
    subset = page(results, index)
    lines = [
        f"Results {index * PAGE_SIZE + 1}–{index * PAGE_SIZE + len(subset)} "
        f"of {len(results)} (capped at 100)"
    ]
    for item in subset:
        lines.append(
            f"\n{item['snippet']}\n{item['posted_at'][:10]} · {item['channel_name']}\n"
            f"https://t.me/{item['username']}/{item['message_id']}"
        )
    buttons = []
    if index:
        buttons.append({"text": "Previous", "callback_data": f"s:{session_id}:{index - 1}"})
    if (index + 1) * PAGE_SIZE < len(results):
        buttons.append({"text": "Next", "callback_data": f"s:{session_id}:{index + 1}"})
    # Plain text prevents source posts injecting HTML/Markdown.
    return message(chat_id, "\n".join(lines)[:4000], buttons)


class Commands:
    async def prepare(self, update, conn):
        callback = update.callback_query
        if callback:
            ack = {"method": "answer_callback_query", "callback_query_id": callback.id}
            try:
                prefix, sid, index = (callback.data or "").split(":")
                if prefix != "s" or not 0 <= int(index) < 20:
                    raise ValueError()
                cur = await conn.execute(
                    """SELECT * FROM search_sessions
                    WHERE id=%s AND owner_id=%s AND expires_at > now()""",
                    (sid, callback.from_user.id),
                )
                session = await cur.fetchone()
                if not session:
                    raise ValueError()
                return [ack, render(callback.from_user.id, sid, session["results"], int(index))]
            except (ValueError, TypeError):
                return [
                    {
                        **ack,
                        "text": "Invalid or expired page. Run /search again.",
                        "show_alert": True,
                    }
                ]
        msg = update.message
        if not msg or msg.chat.type != "private" or not msg.text:
            return None
        command = msg.text.split()[0].split("@")[0] if msg.text.split() else ""
        if command in ("/start", "/help"):
            return [message(msg.chat.id, HELP)]
        if command != "/search":
            return [message(msg.chat.id, "Use /help or /search python async.")]
        try:
            request = parse_search(msg.text)
        except ValueError as error:
            return [message(msg.chat.id, str(error))]
        try:
            async with conn.transaction():  # savepoint: a timeout must not abort the update receipt
                results = await search(conn, request)
        except QueryCanceled:
            return [
                message(msg.chat.id, "Search is temporarily unavailable. Please try again shortly.")
            ]
        if not results:
            return [
                message(
                    msg.chat.id, "No matching posts. Try other English words or a wider date range."
                )
            ]
        sid = secrets.token_hex(8)
        await conn.execute("DELETE FROM search_sessions WHERE expires_at <= now()")
        await conn.execute(
            """INSERT INTO search_sessions(id,owner_id,query,since_date,results)
            VALUES (%s,%s,%s,%s,%s)""",
            (sid, msg.from_user.id, request.query, request.since, Jsonb(results)),
        )
        return [render(msg.chat.id, sid, results, 0)]
