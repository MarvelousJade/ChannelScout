# ChannelScout: measurable impact and resume evidence

## What to measure (and how)

Use **action + technical mechanism + measured result + scope**. A number is defensible only when you can explain its baseline, workload, measurement boundary, evidence and your own contribution.

1. Choose a useful outcome: search latency, relevant results, duplicate suppression or recovery correctness—not lines of code.
2. Define the metric and baseline before running the experiment. Compare equivalent workloads on the same environment; change one factor at a time.
3. Save raw results, software versions, dataset/label identity, commands and limitations. Retain unsuccessful experiments too.
4. Calculate the change from raw values, not rounded table entries. Distinguish percentage reductions from percentage-point gains.
5. Write a qualified claim. Do not convert synthetic results into customer adoption, money saved or production SLAs.
6. Reproduce the experiment and explain the implementation yourself before presenting it as your achievement.

## Recorded results

These are **previously recorded local synthetic measurements**, recalculated and checked in this task—not a new database benchmark. The primary source is [benchmark-final.json](benchmark-final.json), the explicitly labeled final baseline rerun. [impact-metrics.json](impact-metrics.json) preserves full precision, source SHA-256, environment and calculations. This report deliberately uses that run consistently rather than selecting the fastest result across runs.

| Outcome | Baseline → selected condition | Quantified result | Evidence and boundary |
|---|---|---|---|
| Search tail latency | No GIN: p95 5.514 ms → maintained GIN: 4.409 ms | **20.0% lower p95** | 300 DB-client samples per condition; 10,000 synthetic posts; warm, serial reads; no Telegram or pool-wait time |
| Typical search latency | No GIN: p50 4.388 ms → maintained GIN: 3.112 ms | **29.1% lower p50** | Same experiment; not an independent second achievement |
| Search relevance | Raw cover-density ranking: mean P@5 0.000 → length-normalized ranking: 0.933 | **+93.3 percentage points** | 30 template-based, agent-reviewed query labels; two zero-result queries remain |
| Dataset scale | Deterministic corpus | **10,000 posts / 30 topics** | Demonstrated evaluation size, not maximum supported capacity or real indexed content |
| Duplicate correctness | Concurrent delivery of one update | **20 deliveries → one receipt and one stored post** | Historical assertion-backed integration test; not a production error-rate reduction; see [verification.md](verification.md) |

### Formulas

- Latency reduction = `(unindexed_ms - indexed_ms) / unindexed_ms × 100`.
- P@5 per query = `relevant results among first five / 5`; missing results count as non-relevant.
- Mean P@5 = arithmetic mean across **all 30 queries**, including queries returning no results.
- Relevance gain = `(0.933333… - 0) × 100 = 93.3 percentage points`. A relative percentage increase from zero is undefined; do not call this a “93% improvement.”

### Why these figures need qualifications

- The GIN condition includes pending-list cleanup and ANALYZE after bulk loading; the planner then chose bitmap index access. The unindexed condition drops GIN inside a rolled-back transaction. SQL and workload otherwise remain the same.
- The first experiment did **not** show an index benefit. Other preserved runs differ: maintained-run p95 3.801 vs 5.954 ms; later merged-tree p95 3.803 vs 8.509 ms. See [verification.md](verification.md) and [merged raw results](debugging/merged-benchmark.json). There is no repeated-run confidence interval or guaranteed production improvement.
- Quality labels and corpus are template-based and agent-reviewed, not independent human judgments. The synthetic distractors deliberately stress repetition-heavy ranking. “93.3% accuracy on real searches” is not supported.
- Historical test counts and live user confirmations are recorded separately in [live-verification.md](live-verification.md). A test count is coverage evidence, not a business-impact metric.
- No production traffic, active-user count, uptime study, cost reduction or user time-saving study exists. No such impact is claimed.

## Resume bullet candidates

**Use only after you understand the code and can truthfully describe your own role.** Existing implementation, investigation and measurements were agent-performed, with user-reported live demo checks recorded separately. These bullets describe project outcomes, not evidence of independent learner implementation. Do not claim the agent's debugging as your personal investigation.

Choose two or three; the p50 and p95 results belong to the same performance claim.

- Built a Python/FastAPI Telegram search service backed by PostgreSQL full-text search; evaluated retrieval over **10,000 synthetic posts and 30 labeled queries**.
- Reduced **local synthetic database-search p95 latency by 20% (5.51 → 4.41 ms)** with a maintained PostgreSQL GIN index, comparing 300 warmed query samples per condition.
- Tuned PostgreSQL ranking with document-length normalization, raising **mean precision@5 from 0.00 to 0.93 across 30 synthetic labeled queries**, while documenting two remaining no-result cases.
- Implemented transactional ingestion and duplicate handling, with a PostgreSQL integration test verifying **20 concurrent duplicate deliveries produce one receipt and one stored post**.

If “built,” “tuned” or “implemented” overstates your contribution, use a truthful alternative such as “Reproduced and analyzed…” **only after actually doing that work**. Until then, treat these as project evidence and discussion material rather than personal achievement claims. Follow any application-specific disclosure rules concerning AI assistance.

## Reproduce the evidence

### Recalculate existing metrics (no dependencies or database)

From the repository root with Python 3.12+:

```sh
python -m scripts.impact_report
python -m unittest discover -s tests -p test_impact_report.py -v
```

The first command reads `docs/benchmark-final.json` and writes `docs/impact-metrics.json`; it does not access Telegram, read `.env`, seed data or change the database. The tool checks finite positive timings, matching sample counts, equivalent ordered query sets and stored quality means. Tests check the source hash, committed summary, formulas, negative reductions and invalid inputs. This validates derivation and consistency, not the truth of historical execution or relevance judgments.

### Collect a genuinely new benchmark

Use the setup in [README.md](../README.md). **Use only a dedicated disposable synthetic-only database**. The benchmark seeds data and temporarily removes an index. Never use your live/demo database or publish a connection string containing secrets.

```sh
# Set DATABASE_URL to the dedicated synthetic-only database using your shell.
python -m scripts.benchmark --output docs/benchmark-resume-rerun.json
python -m scripts.impact_report --input docs/benchmark-resume-rerun.json --output docs/impact-rerun.json
```

Keep the original reports. Run at least five paired trials, record condition order, inspect query plans and report variation rather than the best run. For stronger relevance evidence, add held-out realistic queries and independent judgments. For perceived latency, separately instrument command receipt through successful Telegram delivery; DB-client latency alone does not measure that workflow.

## This task: checklist, verification and decisions

Acceptance criteria were defined before implementation: reproducible summary, tested calculations, qualified resume claims, explicit fresh-run status, diff review and focused commit.

- [x] Inspect repository instructions and clean Git status; preserve historical raw reports.
- [x] Implement a dependency-free derivation tool and save source-fingerprinted metrics.
- [x] Verify calculations and input rejection: **5 unittest tests passed on Windows Python 3.12.15**.
- [x] Document baseline, scope, limitations, attribution and candidate bullets.
- [x] Ruff lint and format checks passed for the two new Python files; `git diff --check` passed. Ruff was installed only under ignored `.local/impact-tools`; no project dependency was added.
- [ ] Fresh database benchmark/full PostgreSQL integration suite: **blocked in this session**. No Docker/PostgreSQL executable was found on the inspected paths; WSL lists no installed distribution, and the existing POSIX venv is unusable from this Windows shell. Historical timings and test results are not presented as newly rerun.

Decisions:

1. **Reuse preserved raw evidence instead of inventing fresh performance numbers.** An existing controlled report is sufficient for auditable calculations; a fresh DB run would be stronger evidence of current behavior but is runtime-blocked here.
2. **Use stdlib-only reporting and tests rather than add analytics dependencies.** Arithmetic, hashing and JSON require no new packages or credentials. The reporter validates the report structure used here, not an arbitrary benchmark schema or per-sample statistics (which the old report does not retain).
3. **Separate technical outcomes from business impact and personal contribution.** Latency and relevance have evidence; user savings and independent learner debugging do not. This limits how boldly the result can be marketed but keeps it defensible.

## Next evidence to collect yourself

| Question | Method | Record before claiming impact |
|---|---|---|
| Can I reproduce the performance result? | Fresh synthetic DB; repeated paired runs; inspect EXPLAIN | Commit, machine/software, dataset hash, every run, median and range |
| Does search help people find resources faster? | Consenting participants perform equivalent tasks manually and with the bot; counterbalance order | Participant/task counts, success rates, median times, consent and study limitations |
| Does it work on more realistic searches? | Independent relevance judgments on held-out queries | Query/label provenance, per-query scores, no-result cases and failures |
| What did I personally learn/change? | Trace one request, reproduce a defect, write a regression and verify a fix | Your actual notes: problem → hypothesis → evidence → decision → fix → verification |

For a future time-saving claim: `saving_percent = (manual_median - bot_median) / manual_median × 100`. Do not fill in invented numbers. Use the existing [interview guide](interview-guide.md) to prepare explanations, then base your story on your own recorded work.
