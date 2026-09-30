import asyncio

import pytest
from telegram import Update

from channelscout.ingestion import Ingestor


def post(update_id=1, text='python async', date=1700000000, edit=None, chat=-100123):
    message = {'message_id': 7, 'date': date,
               'chat': {'id': chat, 'type': 'channel', 'title': 'Demo', 'username': 'scout_demo'},
               'text': text}
    if edit:
        message['edit_date'] = edit
    return Update.de_json({'update_id': update_id,
                           'edited_channel_post' if edit else 'channel_post': message}, None)


async def stored(db):
    async with db.pool.connection() as conn:
        cur = await conn.execute('SELECT * FROM posts')
        return await cur.fetchall()


async def test_concurrent_duplicate_delivery(db):
    worker = Ingestor(db, {-100123})
    results = await asyncio.gather(*(worker.process(post()) for _ in range(20)))
    assert results.count(True) == 1
    assert len(await stored(db)) == 1
    async with db.pool.connection() as conn:
        cur = await conn.execute('SELECT count(*) AS n FROM processed_updates')
        assert (await cur.fetchone())['n'] == 1


async def test_edits_and_older_event_policy(db):
    worker = Ingestor(db, {-100123})
    await worker.process(post(2, 'new text', edit=1700000200))
    await worker.process(post(3, 'old edit', edit=1700000100))
    await worker.process(post(4, 'delayed original'))
    assert (await stored(db))[0]['body'] == 'new text'
    await worker.process(post(5, 'latest text', edit=1700000300))
    assert (await stored(db))[0]['body'] == 'latest text'
    await worker.process(post(6, 'same second tie', edit=1700000300))
    assert (await stored(db))[0]['body'] == 'same second tie'


async def test_allowlist_and_text_removal(db):
    worker = Ingestor(db, {-100123})
    await worker.process(post(chat=-100444))
    assert await stored(db) == []
    await worker.process(post(2))
    await worker.process(post(3, text='', edit=1700000200))
    assert (await stored(db))[0]['body'] == ''


async def test_transaction_failure_can_retry(db):
    class FailingCommands:
        async def prepare(self, update, conn):
            raise RuntimeError('simulated processing failure')

    with pytest.raises(RuntimeError):
        await Ingestor(db, {-100123}, FailingCommands()).process(post())
    assert await stored(db) == []
    assert await Ingestor(db, {-100123}).process(post())
    assert len(await stored(db)) == 1
