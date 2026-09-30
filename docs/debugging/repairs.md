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

## B — delayed events overwrite edits

**Symptoms/reproduction:** after A was fixed, exercise B still changed `Corrected coroutine examples` back to `Outdated coroutine examples`. New same-second and concurrent-stale-version regressions failed as well. The concurrent test seeded the winning version, then concurrently delivered an older timestamp with a higher ID, a lower ID from the same second, and a delayed original. Stored content ended as `delayed original`.

```sh
pytest tests/test_exercises.py::test_exercise_b_delayed_event tests/test_rework_event_versions.py -q
```

Actual pre-fix result: **3 failed, 1 passed in 9.35s**. The passing case already accepted a later timestamp with a lower update ID; this behavior was preserved, not treated as evidence that the stale-event bug was absent.

**Hypothesis/root cause:** identity protection prevents duplicate rows but does not choose the correct revision. The learning update (and A's intentionally identity-only UPSERT) wrote unconditionally; arrival/lock order determined the final content. Reading versions in Python before updating would introduce another race.

**Fix:** put the strict `(incoming event_at, incoming update_id) > (stored event_at, stored event_update_id)` comparison in PostgreSQL's `ON CONFLICT DO UPDATE ... WHERE`. Source timestamp is primary (`edit_date or date`), and update ID breaks equal-second ties only. Ignore older/equal versions while still committing their update receipt. Do not update the original posting date.

**Tradeoffs:** Telegram does not provide a perfect message-revision identifier. Timestamp precision is one second, and update IDs can reset after long inactivity; the documented tuple is a deterministic policy, not universal source-clock truth. The guard cannot reconstruct content already lost by the faulty implementation. A lower ID with a genuinely newer timestamp must still win. No deletion or exactly-once reply guarantee is added.

**Verification:** **12 passed in 3.94s**, lint passed: all new event tests, original delayed/newer/same-second edits, A's concurrency/recovery checks, original duplicate delivery, allowlist/text removal and rollback/retry. C remains unfixed at this checkpoint; full-suite success is not yet claimed.

**Two-minute interview walkthrough (agent work):** Problem: corrected text reverted. Hypothesis: arrival order was being used as version order. Evidence: delayed older events, equal-second lower IDs and concurrent old arrivals all replaced the seeded winner. Decision: make the version decision part of the row mutation under the database's lock. Fix: strict source-time/update-ID predicate on UPSERT. Verification: stale versions no longer modify content, later timestamps still win even with a lower ID, and receipt/rollback behavior remains intact.

## C — overlapping snapshot pages

**Symptoms/reproduction:** existing tied-result regression still displayed 15 entries with only 13 distinct identities. New parameterized tail tests failed for 6, 10, 11, 12, 15 and 100 results; with 100 results the final page returned IDs 76–80 instead of 95–99. Single-page and invalid-next-page checks passed, showing that basic validation alone did not detect the boundary error.

```sh
pytest tests/test_exercises.py::test_exercise_c_page_boundaries tests/test_rework_pagination.py -q
```

Actual pre-fix result: **7 failed, 5 passed in 16.01s**, including the original tied-result regression. These are synthetic snapshot IDs, not live Telegram messages.

**Hypothesis/root cause:** page headings/buttons/validation used five-item strides, but the slice started at `index * (PAGE_SIZE - 1)`. Page 1 began at item 4 rather than 5, causing overlaps and eventually omitting the true tail. This was not attributed to SQL tie instability; the original missing-tie-breaker experiment had not visibly reproduced that scenario.

**Fix:** slice `[index * PAGE_SIZE : (index + 1) * PAGE_SIZE]`. Preserve the existing negative/out-of-range rejection, unique SQL tie-breakers, owner-bound one-hour snapshots, next/previous controls and top-100 cap. No cursor/keyset infrastructure is needed for a bounded immutable snapshot.

**Tradeoffs:** snapshots still intentionally retain old snippets after edits until expiry/new search. This gives stable boundaries but not live freshness. The regression verifies full/tail pages and complete snapshot coverage, not merely disjoint adjacent pages or headings.

**Verification:** full rework suite **46 passed in 24.41s**, one existing Starlette TestClient deprecation warning. Lint and formatting passed. This includes all three original exercises, all new repair tests, command previous/next round-trip, owner/expiry checks, failure recovery, webhook authentication and real PTB serialization against a fake API. Extra tests/config improvements already on main will be preserved and rerun after the merge.

**Two-minute interview walkthrough (agent work):** Problem: repeated results and missing tail items. Hypothesis: page math was inconsistent with headings. Evidence: boundary tests at 6/10/11/12/15/100 items exposed the wrong start offset; tied-result integration confirmed duplication. Decision: retain the simple immutable snapshot and make its stride consistent. Fix: a page-size start and exclusive end. Verification: exact tail and complete-coverage assertions, navigation tests and the 46-test suite.

## Commit map and pre-merge verification

| Bug | Focused fix commit |
|---|---|
| A — duplicate ingestion + forward schema recovery | `3019afc` |
| B — stale event protection | `1150727` |
| C — snapshot page boundaries | `7f96c54` |

Pre-merge rework tests: 46 passed (one existing Starlette deprecation warning). Lint/format, editable package install, `pip check`, compileall, migration/seed CLI, Compose configuration and real HTTP health/readiness/disabled-webhook checks passed. HTTP smoke waited for startup; initial connection-refused probes were not counted as successes. The restored constraint migration was exercised both on an existing damaged schema and by normal test startup.

```sh
# Dedicated disposable databases only; never use these commands on live data.
TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_rework pytest -q
ruff check channelscout tests scripts
ruff format --check channelscout tests scripts
pip install --no-deps -e .
pip check
python -m compileall -q channelscout scripts
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_rework_benchmark python -m channelscout.cli migrate
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_rework_benchmark python -m channelscout.cli seed
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_rework_benchmark python -m scripts.benchmark --output docs/debugging/rework-benchmark.json
docker compose config --quiet
```

Raw local synthetic report: `rework-benchmark.json`. P@5 remained 0.933 (30 agent-reviewed queries, 10000 posts). Indexed query p50/p95: 3.056/3.677 ms; unindexed: 5.066/7.224 ms. This is serial warmed database-client latency including fetch, not Telegram response time. The 20-read tie-breaker probe again yielded one identity sequence; no unstable-ordering story is invented.

Docker daemon is still unavailable (`docker info` failed to connect); container build/runtime remains blocked. No credentials or hosting authorization were supplied, so real Telegram/deployment tests remain unverified. No GitHub push or hosted CI run was performed in this repair session.

## Merged-main verification

Merged with `git merge --no-ff --no-commit shaoyu/rework` from local main, then inspected/tested the merged tree before recording the merge commit. Git merged automatically without conflicts. Both parents are retained: original main `800fcba` and rework `c802cb3`; all three faulty checkpoints and their three separate fix commits remain visible in history. No reset, squash, history rewrite, force-push or push was used.

Preserved main-only changes: `hide_input_in_errors`, the additional concurrent-edit and secret-canary tests, logical CPU benchmark metadata, original raw benchmark reports and verification corrections. The public-channel explanatory comment was retained. Original faulty tags/learning branch and the local instructor branch were not modified.

Merged-tree suite: **48 passed in 16.69s**, one existing Starlette warning. Lint/format, editable installation, pip dependency check, compileall, migration/seed, synthetic benchmark, tie probe and Compose configuration passed. Final pre-commit rerun: **48 passed in 15.05s**; lint/format and Compose configuration passed again. Real HTTP merged-service smoke returned healthy/ready status and HTTP 404 for the disabled webhook. A post-commit rerun is reported at completion; live Telegram and Docker runtime remain blocked as noted above.

A new reproducible upgrade probe (`scripts/upgrade_probe.py`) requires an EMPTY disposable database. It reconstructs the schema from original main at `800fcba`, seeds 10000 posts plus one receipt, pending outbox intent and search session, then applies the current migration batch twice. Counts and JSONB-row fingerprints matched before/after; no rows required archival. Raw evidence: `main-upgrade.json`. Existing damaged-learning-schema recovery is separately covered by the tests. This establishes both forward paths rather than assuming a fresh database hides migration issues.

```sh
# Create a NEW disposable DB first; probe aborts if any public tables exist.
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_main_upgrade python -m scripts.upgrade_probe --baseline 800fcba
# Full merged suite:
TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_rework pytest -q
# Separate synthetic-only benchmark DB:
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_rework_benchmark python -m scripts.benchmark --output docs/debugging/merged-benchmark.json
```

Merged local synthetic benchmark: P@5 **0.933**, indexed p50/p95 **3.116/3.803 ms**, absent-index **5.605/8.509 ms**. Full query plans and environment are in `merged-benchmark.json`; this is DB-client latency, not Telegram end-to-end performance. Variations from earlier runs are retained rather than presented as guaranteed improvements. The repeated 20-read tie probe still found one sequence; C remains accurately described as a page-stride defect.

The user clarified that the final merge should be committed under the already-configured Shaoyu Git identity. Commit metadata uses that authorized identity; the actual debugging is still agent-performed. No personal learner debugging story is implied by these agent repairs. For interview preparation, reproduce the tests and inspect the diffs yourself, record your own reasoning, and distinguish it from the agent's hypothesis and instructor guidance.
