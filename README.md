# ChannelScout

Indexes posts from approved public Telegram channels and searches them through a bot. A compact Python/FastAPI portfolio project: **one service, one PostgreSQL database**. No frontend, LLM, broker or user-account scraping.

```text
Telegram post/edit ── polling OR authenticated HTTPS webhook ──┐
Telegram /search ──────────────────────────────────────────────┤
                                                             v
                         Ingestor → DB transaction → posts / snapshot / outbox
                                      ^                         |
                              PostgreSQL FTS + GIN              v
                                                   background reply → Telegram
```

## Local setup

Requires Docker Compose and a running Docker daemon. Commands below are from this directory.

```sh
cp .env.example .env
# MODE=off requires no Telegram credentials
```

```sh
docker compose up --build -d
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
docker compose exec scout python -m channelscout.cli seed
```

To search through Telegram: create a bot with BotFather, create a **public demo channel you control**, add the bot as a member (administrator if the channel UI requires it, with minimum permissions), and put its numeric channel ID in `ALLOWED_CHAT_IDS`. No channel discovery tool is provided. Obtain the ID from an update in a private local diagnostic session or Telegram tooling; don't publish raw updates containing personal data.

Set `TELEGRAM_TOKEN`, `ALLOWED_CHAT_IDS=-100...`, and `MODE=polling` in `.env`, then `docker compose up -d --force-recreate scout`. Post a resource in the approved channel; privately message the bot:

```text
/start
/help
/search python async
/search python async --since 2025-01-01
```

Results include snippets, date, channel name, original links, and next/previous buttons. Buttons use a one-hour, owner-bound top-100 snapshot. Run a **new search** after an edit. The synthetic channel's links are intentionally not live; use your own channel for a real demo.

**Do not share one bot token across polling/webhook instances.** Supported deployment is one Uvicorn worker. MODE is one of `off`, `polling`, `webhook`; webhooks disable polling, and polling removes the previous webhook without dropping queued updates.

## Tests and benchmarks (no Telegram credentials)

Tests require a **disposable PostgreSQL database**; fixtures truncate application tables. Never point tests at live data. For host Python:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate; POSIX: source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
# Create a dedicated scout_test DB, then set:
export TEST_DATABASE_URL=postgresql://scout:scout_local_only@localhost:5432/scout_test
pytest -q
ruff check channelscout tests scripts
ruff format --check channelscout tests scripts
# Benchmark needs a dedicated synthetic-only DB; seeds 10000 rows.
export DATABASE_URL="$TEST_DATABASE_URL"
python -m scripts.benchmark --output benchmark-local.json
```

Or create a disposable DB in Compose:

```sh
docker compose exec db createdb -U scout scout_test
docker compose exec -e TEST_DATABASE_URL=postgresql://scout:scout_local_only@db:5432/scout_test scout pytest -q
docker compose exec -e DATABASE_URL=postgresql://scout:scout_local_only@db:5432/scout_test scout python -m scripts.benchmark --output /tmp/benchmark.json
docker compose cp scout:/tmp/benchmark.json ./benchmark-local.json
```

Use PowerShell `$env:NAME='value'` instead of `export` on Windows. Changing the demo password also requires updating DSNs; percent-encode special URL characters. Changing POSTGRES_PASSWORD does not change an existing database volume's password.

## Code map

- `config.py`: env validation and redacted secrets; `logging_config.py`: safe application logging.
- `app.py`: lifecycle, health/readiness and authenticated webhook.
- `transport.py`: polling, decoding and bounded durable delivery.
- `ingestion.py`: atomic receipt and monotonic post UPSERT.
- `search.py`: English FTS, ranking, request parsing and page slices.
- `commands.py`: commands, result snapshots and owner-bound buttons.
- `db.py`, `migrations/`: pool and serialized versioned migrations; `seed.py`, `cli.py`: demo data.

Trace a request: webhook/poll → `Ingestor.process` → `Commands.prepare` → `search` → snapshot + outbox commit → `deliver_one` → PTB `send_message`.

## Access and reliability limits

Checked current [PTB v22.8 documentation](https://docs.python-telegram-bot.org/en/stable/), [Telegram Bot API](https://core.telegram.org/bots/api) and [Bots FAQ](https://core.telegram.org/bots/faq) during implementation. Chose maintained async `python-telegram-bot`, pinned to the checked version. PostgreSQL ranking choices were checked against [current text-search controls](https://www.postgresql.org/docs/current/textsearch-controls.html).

- Bots receive channel messages where they are members; public visibility alone does not grant access. An allowlist additionally gates storage. This app ignores private channels and non-channel ingestion.
- Bot API has no general arbitrary channel-history retrieval method. Index future incoming updates after setup; missed history is not backfilled. Telegram holds updates no longer than 24 hours. Bot accounts cannot initiate conversations with users who never started them.
- `edited_channel_post` delivers edits of posts known to the bot. Text/caption removal stores empty text; media itself is not indexed.
- Ordinary channel-post deletion notifications are not provided by the Bot API (business-message deletion updates are different). Deleted posts may remain searchable; links may fail. Owner-operated cleanup/reconciliation is future work. No claim of reliable deletion tracking.
- English stemming/stopwords only; no synonyms, fuzzy or semantic search. `parser` and `parsing` need not match. Date filter uses UTC midnight.
- Receipt, post mutation, snapshot and reply intent commit atomically. **Exactly-once DB effects are not exactly-once outbound replies**; a crash/ambiguous timeout can duplicate a reply. Delivery stops after five failed attempts; failures remain in outbox for inspection.
- Application logs exclude update bodies, queries and personal IDs; infrastructure must also avoid Bot API URLs and secret headers. Sessions contain user IDs/queries for one hour; expired sessions are deleted on a new successful search. Sent outbox/receipts persist until operator maintenance. This is a controlled demo, not a public multi-tenant production deployment.

## Evidence and interview material

- [Verification](docs/verification.md): original local results and blockers.
- [Docker/live verification](docs/live-verification.md): container checks, observed Telegram search and snippet-formatting repair.
- [Engineering decisions](docs/engineering-decisions.md): alternatives, evidence, limits.
- [Deployment](docs/deployment.md), [demo script](docs/demo.md).
- [Interview guide](docs/interview-guide.md): trace the code rather than memorize claims.
- [Debugging exercises](docs/debugging/README.md): original faulty checkpoints remain available.
- [Autonomous repair report](docs/debugging/repairs.md): authorized solutions, regression evidence, individual fix commits and non-squashed local merge (spoilers).

**Status:** 50 tests pass on native PostgreSQL and in Docker. Docker startup/health/readiness and a live channel-post/private-bot search were observed. The user confirmed clean live snippets and edited-post search results; DB checks confirmed one post row and retention of its original date/link. Live Next/Previous pagination was also confirmed by the user and a read-only snapshot check. Hosted webhooks, GitHub-hosted CI and deployment remain unverified. See the verification records for commands and limitations.
