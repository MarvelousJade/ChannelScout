import pytest

from channelscout.search import SearchRequest, page, parse_search, search
from channelscout.seed import seed


@pytest.mark.parametrize(
    "text",
    [
        "/search",
        "/search !!!",
        "/search python --since bad",
        "/search python --since 2025-02-30",
        "/search " + "x" * 201,
    ],
)
def test_invalid_search(text):
    with pytest.raises(ValueError):
        parse_search(text)


def test_date_parse_and_pages():
    request = parse_search("/search@ChannelScoutBot python async --since 2025-01-02")
    assert str(request.since) == "2025-01-02"
    assert request.query == "python async"
    results = list(range(12))
    assert page(results, 0) == [0, 1, 2, 3, 4]
    assert page(results, 1) == [5, 6, 7, 8, 9]
    assert page(results, 2) == [10, 11]
    with pytest.raises(ValueError):
        page(results, -1)


async def test_rank_date_and_deterministic_ties(db):
    await seed(db)
    async with db.pool.connection() as conn:
        results = await search(conn, SearchRequest("python async"))
        assert len(results) == 100
        assert all("python" in x["snippet"] and "async" in x["snippet"] for x in results)
        assert results == await search(conn, SearchRequest("python async"))
        keys = [(-r["rank"], r["posted_at"], r["chat_id"], r["message_id"]) for r in results]
        assert all(results[i]["rank"] >= results[i + 1]["rank"] for i in range(99))
        tied = [
            r
            for r in results
            if r["rank"] == results[0]["rank"] and r["posted_at"] == results[0]["posted_at"]
        ]
        assert [r["message_id"] for r in tied] == sorted(r["message_id"] for r in tied)
        assert len(keys) == len(set(keys))
        assert not await search(conn, parse_search("/search python async --since 2026-01-01"))
        assert not await search(conn, SearchRequest("nonexistentzzzz"))
        assert not await search(conn, SearchRequest("the and"))
