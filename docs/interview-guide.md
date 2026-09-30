# Interview guide — adapt after your own investigation

This implementation and its initial decisions/tests were AI-agent-authored. Do not claim personal implementation, bug discovery or production impact you have not performed. Reproduce the setup, trace the code and record your own changes first.

## 60-second introduction (project description, not an experience claim)

“ChannelScout is a small Telegram search bot backed by Python, FastAPI and PostgreSQL. It indexes future text posts and edits from approved public channels. A search returns ranked snippets with original links and snapshot pagination. The database has separate identities for posts and received updates, so replayed deliveries do not duplicate stored effects. Edits have a version guard to reject older events. Webhook acknowledgement happens after the database transaction commits, and a durable outbox retries replies. That does not mean exactly-once Telegram delivery. The project includes deterministic data, local PostgreSQL tests and synthetic search measurements; live deployment remains to be verified.”

## Three-minute technical walkthrough

- **0:00–0:45:** Open `app.py` lifecycle and webhook; explain exclusive MODE values, secret header, and polling offset in `transport.py`. One service, one database, no broker.
- **0:45–1:30:** Trace `Ingestor.process`. Point to unique receipts and post keys in migration 001. Show tuple comparison in the UPSERT. Explain concurrent `ON CONFLICT` behavior and rollback.
- **1:30–2:15:** Trace `Commands.prepare` → `search`. Explain generated `tsvector`, GIN, English AND matching, rank normalization and tie-breakers. Sessions store top-100 snippets for one hour, owner-bound; buttons page the snapshot.
- **2:15–3:00:** Follow outbox insert to `deliver_one`. Explain bounded retries, retry_after, terminal failures and crash-after-send ambiguity. Show actual synthetic benchmark plans and the unsuccessful first run. Name limitations without promising production performance.

## Stack concepts and follow-up questions

- Python `async` is cooperative I/O, not parallel CPU execution. Where would a blocking operation stall this service?
- FastAPI lifecycle starts/cancels workers; health is process liveness, readiness is DB/schema. What happens when Telegram is down but DB is healthy?
- PostgreSQL uniqueness arbitrates concurrent updates; a prior existence check cannot replace a constraint. What does the losing INSERT wait for?
- A transaction commits receipt + mutation + reply intent together. Why must a failed statement use a savepoint if we want a temporary-failure reply?
- `tsvector` stores lexemes; `tsquery` defines matching; GIN finds candidates, while rank/date/identity sorting orders them. Why doesn't normalization 32 change rank ordering? Why did GIN initially not get used?
- Why are date and unique identity tie-breakers needed? What staleness does snapshot pagination intentionally accept?
- Why can't a transaction spanning DB and Telegram guarantee exactly-once replies? Could an idempotency key help if Telegram supported one?
- What does webhook secret validation protect against, and what does it not protect against? How would you limit body sizes and abusive authorized bot usage?
- Why can a bot not backfill arbitrary channel history or reliably detect normal channel deletions? How would you communicate stale results?
- What evidence would justify fuzzy search, embeddings, a broker, multiple workers or larger connection pools?

## Debugging stories — complete only after you investigate

For each exercise, write your actual notes:

**Problem → hypothesis → evidence (command/output) → decision → fix (diff) → verification.**

Identify which hypotheses were your own and which came from hints or AI. Include unsuccessful experiments. No learner investigation has happened yet; no personal debugging story is supplied.

## Later autonomous debugging walkthroughs

The user authorized the agent to repair the exercises autonomously. Actual commands, failing regressions, tradeoffs and individual fix commits are in [repairs.md](debugging/repairs.md). These are real local debugging observations of deliberately injected defects, **not production incidents or evidence of your independent investigation**.

- **Duplicate ingestion:** problem—concurrent deliveries produced repeated rows; hypothesis—absence checks were unprotected; evidence—same-update counts `(2,2)` and distinct updates creating two posts; decision/fix—database uniqueness, atomic receipt claims and UPSERT, plus an archival forward migration; verification—race, recovery, FK/PK and rollback tests pass.
- **Stale edits:** problem—revised text reverted; hypothesis—arrival order controlled state; evidence—older timestamps, same-second lower IDs and concurrent older arrivals replaced the winner; decision/fix—strict event-time/update-ID comparison in the UPSERT; verification—older events ignored, newer timestamps accepted, original posting date retained.
- **Pagination:** problem—overlapping results and incorrect tail pages; hypothesis—inconsistent page math; evidence—15 entries contained 13 identities, and a 100-result tail returned 76–80 instead of 95–99; decision/fix—use the same five-item stride for slices and controls; verification—exact tail, coverage, tied-score integration and navigation checks pass.

The merged tree passes 48 tests. An upgrade probe preserved fingerprints of 10000 baseline posts and a receipt, pending reply and search session. Follow-up questions: Why is an application lock insufficient? How do you choose an ambiguous duplicate survivor without pretending to know source truth? Why archive removed rows? Why must stale checking occur inside the mutation? What freshness does snapshot pagination sacrifice? How can a non-squashed merge preserve repairs when main already had correct baseline behavior?

After reproducing this work yourself, replace these agent descriptions with your actual notes and identify where instructor/AI guidance influenced your decisions.

## Suggested resume bullets (project facts, use only after understanding/reproducing)

- ChannelScout: Python/FastAPI Telegram integration with PostgreSQL full-text search, owner-bound pagination, allowlisted post/edit ingestion and transactionally deduplicated update processing; verified locally using PostgreSQL and a simulated Telegram API.
- Built reproducible synthetic search evaluation over 10000 posts and 30 agent-reviewed queries; selected length-normalized ranking with mean precision@5 of 0.933, documented vocabulary failures and indexed/unindexed local query plans.

These describe agent-built project functionality, not independent work, live deployment, customer impact or production outcomes. Revise attribution before using them as personal experience claims.
