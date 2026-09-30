# Five-minute demo script

1. Start Compose with MODE=off; show `/health` and `/ready`. Seed 10000 deterministic posts. Explain that synthetic links are not real.
2. Run the credential-free test suite on a separate disposable DB. Show duplicate/update-order regressions and `docs/benchmark.json`.
3. With **authorized credentials**, set MODE=polling and the allowlisted channel ID. Post `Python async tutorial with coroutine examples` in your public demo channel. Send `/search python async` privately to the bot; show snippet/date/channel/link.
4. Edit that post to `Python async tutorial with cancellation examples`. Run a **new** search and show updated content. Existing button sessions deliberately keep their snapshot.
5. Post enough matching resources to show next/previous buttons. Try `/search`, an invalid date and a nonexistent term.
6. Explain the DB identity, version tuple and outbox acknowledgement boundary. A reply can still duplicate if Telegram accepted it before a crash.
7. Show focused commits and the isolated learning branch. Describe defects as exercises, not personal discoveries or production incidents.

Steps 3–5 require a live bot and were not performed during this build. For a no-credentials demo, the tests run the same ingestion/search/outbox workflow against PostgreSQL and serialize replies through a fake Telegram API. Do not present that as a live Telegram demonstration.
