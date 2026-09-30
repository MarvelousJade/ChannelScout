import argparse
import asyncio

from .config import Settings
from .db import Database
from .seed import seed


async def run(command):
    db = Database(Settings().database_url.get_secret_value())
    await db.open()
    try:
        await db.migrate()
        if command == 'seed':
            await seed(db)
    finally:
        await db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['migrate', 'seed'])
    asyncio.run(run(parser.parse_args().command))
