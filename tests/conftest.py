import os

import pytest

from channelscout.db import Database


@pytest.fixture
async def db():
    # Mandatory real PostgreSQL, never silently skip. Must be a disposable database.
    url = os.environ.get('TEST_DATABASE_URL', 'postgresql://nobody@127.0.0.1:55432/scout_test')
    database = Database(url)
    await database.open()
    await database.migrate()
    async with database.pool.connection() as conn:
        await conn.execute('TRUNCATE posts, outbox, processed_updates, search_sessions CASCADE')
    yield database
    await database.close()
