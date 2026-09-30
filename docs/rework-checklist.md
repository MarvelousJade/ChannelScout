# Autonomous exercise repair checklist

User authorized autonomous repairs, consulting instructor notes, and a non-squashed local merge into main. No push, force-push, history rewrite, or reset is authorized. Initial working tree was clean. Local main created from origin/main at 800fcba; shaoyu/rework created from the learning branch at 594eb77. Original faulty branches/tags remain unchanged.

Acceptance criteria (defined before repairs):
- [x] A: reproduce duplicate delivery and add a new failing regression for distinct updates targeting one post. Restore atomic DB-enforced identities. Test fresh schemas and forward recovery of an already-damaged learning schema; retain discarded rows in a one-off audit archive. Make one focused fix commit with documentation.
- [x] B: reproduce delayed stale content, add a failing concurrent/same-second event regression, and guard the mutation atomically by the event-version tuple. Preserve original posting date. Make one focused fix commit with documentation.
- [x] C: reproduce overlapping pages, add a failing tail/boundary regression, and use a consistent page-size stride while preserving snapshot ownership/expiry and deterministic ordering. Make one focused fix commit with documentation.
- [x] Rework: run complete tests, lint/format, package install, migrate/seed, benchmark and HTTP smoke against dedicated disposable PostgreSQL databases. Record live Telegram/Docker/deployment blockers honestly.
- [ ] Merge: merge shaoyu/rework into local main with --no-ff, preserving useful config redaction, extra concurrency coverage and evidence already on main. Rerun required checks and inspect the merge diff. Leave everything committed and report individual fix hashes + merge hash. Do not push.

All investigation and repairs in this checklist are agent-performed practice work, not learner discoveries or production incidents. Instructor notes were consulted explicitly; interview material must retain that attribution.
