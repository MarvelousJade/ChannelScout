# Verification record

All observations below are local and agent-performed. No production traffic, customer impact, learner investigation, live bot or hosted deployment is claimed.

## Environment and reproducibility

- WSL2 Linux x86_64, Python 3.14.7, PostgreSQL 18.6; full server/platform strings and measured package versions are in `benchmark.json`.
- Dependencies pinned in `requirements.lock`; deployment/CI targets Python 3.12. Python 3.12 CI/container execution remains unverified locally.
- Docker client 27.5.1 / Compose 2.33.1 available, **daemon unavailable**. `docker compose config --quiet` passed; image build and Compose startup did not run.
- Host Python initially had a broken pip bootstrap (`pyexpat` library mismatch); isolated downloaded library/package files and a repo-local ignored venv allowed tests without replacing system libraries. PostgreSQL ran locally on loopback port 55432 with a dedicated disposable `scout_test` database. Isolated artifacts under `.local/` are ignored, not shipped.
- Native local benchmark storage: `/var/lib/channelscout-test`; not the Docker-volume environment. Trust authentication was used only for this isolated loopback test instance. Do not use that in deployment.

Commands run from repo root (POSIX). The local session also set `LD_LIBRARY_PATH` to ignored isolated libraries; ordinary healthy Python/PostgreSQL installations do not need that workaround.

```sh
TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_test PTB_TIMEDELTA=1 pytest -q
ruff check channelscout tests scripts
ruff format --check channelscout tests scripts
docker compose config --quiet
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_test python -m channelscout.cli seed
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_test python -m scripts.benchmark --output docs/benchmark.json
DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_test python -m scripts.pagination_probe
```

## Functional checks

Latest baseline run: **29 tests passed**, lint and formatting checks passed. No Telegram credentials. Tests use actual PostgreSQL, fake Telegram responses and actual PTB request serialization. Fixtures truncate app tables and must never run on a live DB.

Covered: migrations/seed repeatability; concurrent duplicate receipt claims; allowlist; post text removal; newer edits, delayed originals/edits and same-second ties; processing rollback/retry; relevance, stable ordering, date filters; snapshots, ownership/expiry/previous-next; invalid/no-results input; secret redaction; webhook header/body/replay and 503 recovery; search timeout response; rate-limit deadlines, permanent errors, five-attempt exhaustion; polling offset commit boundary. Exercise regressions pass on baseline.

A 20-way duplicate delivery produced one successful receipt and one stored post. Delayed events preserved corrected content; a later edit replaced it. Failure after post mutation rolled back both receipt and post, then retry succeeded. These outcomes are asserted, not inferred from log text.

The initial service HTTP smoke used only a 2-second wait and failed to connect. Commit `a1d3881` incorrectly described that smoke as verified. A subsequent bounded startup-wait run returned `{"status":"alive"}` twice. This correction is preserved rather than rewriting history. Final database-backed HTTP smoke used a bounded startup wait and returned `{"status":"alive"}` and `{"status":"ready"}`.

Final code inspection found that Pydantic model-level configuration errors could include the original input token despite SecretStr repr redaction. A regression using a synthetic canary token was run and failed. Enabling `hide_input_in_errors` removed it from the exception text; the regression was rerun before committing. This was an agent-discovered local issue, not a learner or production incident. The structured log filter remains an additional safeguard.

Warnings: installed Starlette warns that its httpx TestClient support is deprecated. It still runs successfully; migration to its new client is future maintenance. PTB retry_after deprecation is avoided with PTB_TIMEDELTA=1; implementation accepts both int and timedelta.

## Dataset and labels

`seed.py` deterministically creates 10000 final post rows in synthetic channel -100999, interleaving 30 developer-resource topics, repeated terms, tied scores/dates, 1428 mention-only promotions and 1000 revised rows. Edited seed rows represent final versions; event replay is tested separately. No real channel names, user content or live message links are included.

`evaluation/queries.json` has 30 **agent-reviewed**, template-based relevance judgments. Rule: resource IDs whose `(id-1) % 30` equals the query's topic are relevant except IDs divisible by 7 (promotion-only). This enumerates labels independently of retrieved rankings. All 10000 IDs are deterministically labelable. Not independent human assessment; a learner/reviewer should inspect and revise these judgments. Hash of label bytes is stored with results.

Precision@5 = relevant results in the first five / 5, with missing results counted as non-relevant. Report the arithmetic mean over all 30 queries, including zero-result queries; not precision conditional on successful retrieval.

| Rank normalization | Mean precision@5 | Observation |
|---|---:|---|
| 0 (raw cover density) | 0.000 | Repetition-heavy promotions dominated |
| 32 (rank/(rank+1)) | 0.000 | Monotonic transform didn't change ordering |
| 2 (divide by length; selected) | 0.933 | 28 queries score 1.0; `regex parser`, `api page` return nothing |

The ranking regression was run before changing the default and failed; it passed after normalization 2. This is synthetic stress-case evidence, not real-user relevance or a general guarantee.

## Search latency and query plans

Measured serial DB-client execution+fetch of the same production SQL (rank/sort/snippet, max100) after five warmups, 10 passes × 30 queries = 300 samples per condition. Excludes connection acquisition, queue wait, bot API latency and user-perceived Telegram response time. p50 is median; p95 is sorted sample at floor((n-1)*0.95). No concurrent load, cold-cache or multi-run confidence interval. Order of conditions is fixed; cache/order effects remain.

| Run/condition | p50 ms | p95 ms | Representative plan |
|---|---:|---:|---|
| First, GIN present | 4.403 | 5.725 | Seq Scan |
| First, index absent | 4.273 | 5.324 | Seq Scan |
| Maintained GIN | 3.040 | 3.801 | Bitmap Index Scan + Bitmap Heap Scan |
| Index absent | 4.545 | 5.954 | Seq Scan |

The first experiment showed no index improvement. Bulk-loaded GIN pending entries were then cleared explicitly with `gin_clean_pending_list` and statistics refreshed with ANALYZE. The planner—not forced scan settings—selected GIN afterward. The absent-index condition really drops the index inside a rolled-back transaction. It restores the schema automatically. Both raw reports contain full `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` and software versions. Maintenance is part of the second experiment, not hidden. Do not extrapolate these timings to production or Telegram end-to-end response time.

## Pagination experiment

`pagination_probe` removes unique tie-breakers in a non-mutating experimental SQL string, then repeats 20 serial reads of tied synthetic results. Actual result: **1 distinct identity sequence**. Missing tie-breakers are unsafe, but instability was not visibly reproduced here. Exercise C therefore uses another ordinary page-boundary defect, recorded in the separate instructor branch; learner instructions disclose symptoms only.

## Not verified / blockers

No real bot token/channel/hosting authorization: live Telegram commands, permissions, post/edit notifications, outbound formatting, callbacks, hosted HTTPS secret headers and deployment were not tested. Docker daemon unavailable: Compose image build/start and container tests blocked. GitHub Actions is authored, not executed remotely; nothing was pushed. Exactly-once outbound delivery, channel deletions, backfill, HA, public abuse resistance and production load are not promised.

## Final checks

Baseline: 29 tests passed, one Starlette deprecation warning; lint/format, deterministic seed CLI, real HTTP health/readiness, Compose configuration and diff whitespace checks passed. Exercise checkpoints and the final post-exercise baseline rerun remain to be recorded in `debugging/evidence.md`.
