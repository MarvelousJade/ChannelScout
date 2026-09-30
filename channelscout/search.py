from dataclasses import dataclass
from datetime import date
import re


PAGE_SIZE = 5
RESULT_LIMIT = 100


@dataclass
class SearchRequest:
    query: str
    since: date | None = None


def parse_search(text):
    tokens = text.split(maxsplit=1)
    if not tokens or tokens[0].split("@")[0] != "/search" or len(tokens) != 2:
        raise ValueError("Use /search python async [--since YYYY-MM-DD]")
    query = tokens[1].strip()
    since = None
    if "--since" in query:
        match = re.fullmatch(r"(.+?)\s+--since (\d{4}-\d{2}-\d{2})", query)
        if not match:
            raise ValueError("Date filter must be --since YYYY-MM-DD at the end.")
        query, day = match.groups()
        try:
            since = date.fromisoformat(day)
        except ValueError:
            raise ValueError("Invalid calendar date.") from None
    if not query or len(query) > 200 or not any(c.isalnum() for c in query):
        raise ValueError("Search requires 1–200 characters including a word or number.")
    return SearchRequest(query, since)


SEARCH_SQL = """WITH q AS (SELECT plainto_tsquery('english', %s) AS query)
    SELECT chat_id, message_id, channel_name, username, posted_at,
           ts_headline('english', body, q.query,
                       'StartSel=, StopSel=, MaxWords=20, MinWords=8') AS snippet,
           ts_rank_cd(document, q.query, %s) AS rank
    FROM posts CROSS JOIN q
    WHERE document @@ q.query AND (%s::date IS NULL OR posted_at >= %s::date)
    ORDER BY rank DESC, posted_at DESC, chat_id ASC, message_id ASC
    LIMIT %s
"""


async def search(conn, request, normalization=32):
    cur = await conn.execute(
        SEARCH_SQL, (request.query, normalization, request.since, request.since, RESULT_LIMIT)
    )
    rows = await cur.fetchall()
    return [
        {**row, "posted_at": row["posted_at"].isoformat(), "snippet": row["snippet"][:240]}
        for row in rows
    ]


def page(results, index):
    if index < 0 or index * PAGE_SIZE >= len(results):
        raise ValueError("Invalid page.")
    return results[index * PAGE_SIZE : (index + 1) * PAGE_SIZE]
