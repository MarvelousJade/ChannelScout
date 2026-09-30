# Actual engineering decisions (agent-authored)

## 1. Search quality versus complexity — two-minute explanation

**Problem:** literal repeated mentions are not necessarily useful resources. Keep English search explainable without embedding services or LLMs.

**Alternatives tested:** PostgreSQL `plainto_tsquery` AND matching plus `ts_rank_cd` with normalization 0, 32 (rank/(rank+1)), or 2 (divide by document length). English stemming is built in; no synonym dictionary or custom term rewriting. Normalization 32 is monotonic and cannot fix ordering by itself.

**Evidence:** 10,000 deterministic synthetic posts, including 1,428 mention-only marketing distractors and 1,000 revised final versions. Thirty agent-reviewed queries label tutorial/example resources relevant, promotions irrelevant. Normalization 0 and 32 both scored mean precision@5 0.000; normalization 2 scored 0.933. A new regression assertion first failed with the old default; it passed after changing to 2. These templates are intentionally constructed stress cases, not representative relevance judgments from real users. Independent human label review is still needed.

**Decision:** length-normalized cover-density rank, then date descending and unique chat/message identity ascending. Keep the GIN index. After clearing its bulk-load pending list, the planner selected bitmap GIN access; the first unmaintained experiment instead chose sequential scans and showed no index improvement. Raw plans and timings are preserved in `benchmark-first.json` and `benchmark.json`.

**Tradeoffs:** short documents can be favored excessively. Literal English stemming does not equate `parser` with `parsing`, or `page` with `pagination`; those two evaluation queries failed. No fuzzy, semantic, multilingual or prefix search. Expand labels before adding query rewriting. Date filtering is inclusive from UTC midnight.

## 2. Durable webhook processing — two-minute explanation

**Problem:** Telegram can retry an update, and a process can crash between modifying a post and acknowledging delivery.

**Alternatives:** acknowledge immediately and use an in-memory queue (loses work on crash); synchronously send the reply before acknowledgement (slow and couples DB ingestion to Telegram availability); add a separate broker/worker (unnecessary infrastructure here).

**Decision:** one service with a PostgreSQL-backed outbox. In one transaction claim `update_id`, apply a version-guarded post change, or search and create a one-hour result snapshot, then enqueue reply intent. Return HTTP 200 only after commit. Failures return 503 so Telegram may retry. Polling advances its offset only after the same transaction completes. Search statement timeouts use a savepoint and enqueue a clear temporary-failure response.

**Evidence:** concurrent duplicate tests, forced rollback and retry, webhook authentication/replay/503 recovery, polling failure-offset checks, retry_after scheduling, terminal failures and actual PTB serialization against a fake HTTP API all pass against PostgreSQL.

**Boundary:** a background coroutine locks one pending outbox row during bounded sends, records success afterward, and retries transient failures up to five attempts. A crash after Telegram accepts a reply but before DB commit can resend it. Deduplicated DB effects do **not** guarantee exactly-once outbound replies. There is no Telegram send idempotency key. Permanent errors or exhausted attempts leave inspectable failed rows; no claim of guaranteed eventual replies. Pending rows survive restart. Callback acknowledgements may expire and are best-effort. Database downtime prevents both ingestion and delivery.

**Tradeoffs:** network calls hold a DB row lock/connection (at most 12 seconds per action). Single instance/one Uvicorn worker is the supported deployment. No broker, distributed coordination, automatic failover or reply-order guarantee across concurrent requests. Sessions and receipts need periodic retention maintenance for a long-running deployment.

## Event and pagination policy

- Identity is `(chat_id, message_id)`; `update_id` receipt is unique and claimed atomically.
- New content wins only if `(edit_date or date, update_id)` is strictly greater than the stored tuple. Telegram timestamps have second precision, so update_id breaks equal-second ties. No higher-ID but older-timestamp event may overwrite a newer edit.
- Telegram may choose a random next update_id after a week without updates. Timestamp remains primary; equal-second tie-breaking across that rare reset is not a perfect source revision identifier.
- Posted date remains the initial message date; edited content retains it.
- Search stores the top 100 ordered snippets/links in a one-hour owner-bound DB session. Next/previous slice this immutable snapshot, not live OFFSET queries. A new search sees edits; existing snapshots can show old content and links that no longer work. This bounded staleness is deliberate.
