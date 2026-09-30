# Implementation checklist

New standalone repository; parent directory has no valid Git repository or applicable AGENTS.md. No existing files changed. Branch: `codex/channelscout`. Commits are agent-authored, not the learner's work.

Acceptance criteria before each increment:
- [ ] Service: env validation, redacted secrets, liveness/readiness tests; runnable HTTP smoke.
- [ ] Storage: versioned migration, unique identities, deterministic 10k seed; real PostgreSQL tests.
- [ ] Ingestion: allowlist, duplicate replay, concurrent delivery, stale/new edit and rollback tests.
- [ ] Search: English FTS + GIN, rank/date/unique ordering, date filters, pagination and relevance tests.
- [ ] Transport: commands, bounded retries, durable reply queue, authenticated webhook, exclusive polling; mocked Telegram tests.
- [ ] Evidence: 30 labeled queries, actual quality/latency/plans; CI, setup/deployment, interview docs.
- [ ] Learning: separate defective branch, reproducible failing regressions; baseline remains passing; solutions not exposed in learner guide.
- [ ] Final: full tests, seed/benchmark and HTTP smoke, diff review, clean committed branch.

Verification boundary: credentials/hosting are not supplied. Real Telegram posting/editing and deployment are not authorized or verified. Docker daemon is unavailable at initial inspection; attempt real local PostgreSQL rather than substituting SQLite.

Documentation checked via browser: PTB stable documentation currently identifies v22.8; async Bot API chosen (no user-account scraping). Telegram Bot API and FAQ confirm mutually exclusive transports, 24-hour update retention, channel membership visibility, known-post edits, secret header, retry_after. Sources and limits will be recorded in README.
