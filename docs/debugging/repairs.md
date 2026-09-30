# Autonomous repairs of the three practice defects

These defects were deliberately introduced by the build agent on `codex/channelscout-learning`, not production incidents. The user then authorized autonomous investigation, consulting the local instructor notes, separate fixes and a non-squashed local merge into main. All work below is **agent-performed**; it is not evidence of the learner's independent debugging experience. Original faulty tags and branches remain unchanged.

## Setup and original reproduction

Working tree was clean. `origin/main` and the implementation branch were at `800fcba`; local main was created at that commit. `shaoyu/rework` started at learning checkpoint `594eb77`. Instructor notes on `codex/channelscout-instructor` were consulted and compared with the actual source and test failures.

Local environment: Python 3.14.7, PostgreSQL 18.6, PTB 22.8, WSL2. A new disposable `scout_rework` DB was created on loopback 55432; no live or pre-existing practice database was truncated by this repair session. Commands use the local venv and isolated libraries from the earlier verification setup.

```sh
export TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_rework
export PTB_TIMEDELTA=1
pytest tests/test_exercises.py -q
```

Actual initial result: **3 failed in 7.61s**, with duplicate counts `(2,2)`, reverted edited content, and 15 page entries containing only 13 unique identities.

## A — duplicate ingestion

**Symptoms/reproduction:** two concurrent deliveries of one update created two receipts and two stored posts. Existing exercise A reproduced `(2,2)` instead of `(1,1)`. A *new* regression, `test_distinct_updates_share_one_post_identity`, scheduled overlapping reads for two distinct update IDs targeting the same message; it failed with two posts instead of one before the fix. This checks that receipt uniqueness alone is not enough.

```sh
pytest tests/test_rework_duplicates.py::test_distinct_updates_share_one_post_identity -q
```

**Hypothesis/root cause:** application-level SELECT-before-INSERT checks did not reserve missing rows. Migration 004 had removed the receipt/post constraints and outbox FK, so PostgreSQL could not arbitrate either identity. Controlled interleaving demonstrated the race without artificial application crashes or sleeps.

**Fix:** restore primary keys and FK through additive migration 005; claim receipts using atomic `INSERT ... ON CONFLICT DO NOTHING RETURNING`, and UPSERT posts by `(chat_id,message_id)`. Keep receipt, post and outbox in one transaction. No in-process lock is needed. This commit addresses identity only; event-order protection is the next separate repair.

**Already-damaged data:** 005 keeps the greatest event-time/update-ID tuple per post, retains the earliest receipt timestamp per update, and archives every discarded row as JSONB in `ingestion_repair_archive`. Equal-version content conflicts use a documented lexical tie-breaker (C collation) and preserve alternative rows in the archive; the migration cannot infer which equally versioned text was truly intended. Exact duplicate physical ties are interchangeable. The survivor's recorded original posting date remains unchanged. Previously overwritten content that no longer exists cannot be reconstructed.

**Tradeoffs:** repair takes table locks under the existing migration transaction/advisory lock and can fail on a large dataset under the bounded statement timeout; failure rolls back. An orphaned outbox causes FK restoration to fail rather than deleting reply intents. Archive records contain original stored data and need the same access controls/retention care as posts. In a real deployment, back up first and review ambiguous survivors. The intentionally faulty historical 004 is not rewritten: fresh/main databases apply 004 and 005 within one transaction, so removed protection never becomes externally visible during a successful migration batch.

**Verification:** new regression initially **1 failed in 5.60s**. After repair, **7 passed in 8.32s**: distinct-update identity, damaged-schema recovery/archive/constraints, rollback on invalid FK, original exercise A, 20-way duplicate delivery, allowlist/text removal and rollback/retry. Lint passed. Recovery test preserves unrelated posts and pending outbox linkage, verifies both PKs and FK, and checks that all four discarded test rows are archived. Repeat migration is covered by the existing storage test in the final suite. B and C remain deliberately unfixed at this checkpoint; no full-suite pass is claimed yet.

**Two-minute interview walkthrough (agent work):** Problem: repeated database rows. Hypothesis: concurrent absence checks were not protected. Evidence: controlled same-update and distinct-update deliveries both duplicated posts. Decision: let PostgreSQL enforce identities rather than add a process lock. Fix: unique claims plus UPSERT, with a forward recovery migration for damaged schemas. Verification: seven targeted real-PostgreSQL checks, including preservation/rollback of repair data. Explain that this prevents duplicate DB effects, not exactly-once Telegram replies.

## B — pending autonomous repair

## C — pending autonomous repair

## Final merge/checks — pending
