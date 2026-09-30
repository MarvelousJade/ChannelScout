from channelscout.seed import rows, seed


async def test_migrations_and_repeatable_seed(db):
    await db.migrate()
    await db.ready()
    await seed(db)
    await seed(db)
    async with db.pool.connection() as conn:
        cur = await conn.execute('SELECT count(*) AS n FROM posts')
        assert (await cur.fetchone())['n'] == 10000
        cur = await conn.execute("SELECT indexname FROM pg_indexes WHERE indexname='posts_document_gin'")
        assert await cur.fetchone()
    assert list(rows(10)) == list(rows(10))
    assert 'Revised' in list(rows(10))[-1][5]
